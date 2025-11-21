"""WebSocket consumers for real-time chat"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatSession, Message
from .ai_engine import AIEngine
from .escalation import EscalationHandler


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""
    
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Receive message from WebSocket"""
        data = json.loads(text_data)
        message = data.get('message', '')
        message_type = data.get('message_type', 'user')
        
        # Process message
        if message_type == 'user':
            await self.handle_user_message(message)
        elif message_type == 'agent':
            await self.handle_agent_message(message, data.get('user_id'))
    
    async def handle_user_message(self, message):
        """Handle user message and generate AI response"""
        # Save user message
        session = await self.get_session()
        if not session:
            await self.send(text_data=json.dumps({'error': 'Session not found'}))
            return
        
        await self.save_message(session, 'user', message)
        
        # Process with AI
        ai_engine = AIEngine()
        ai_response = ai_engine.generate_response(message, self.session_id)
        
        # Save AI response
        await self.save_message(session, 'ai', ai_response['response'], 
                               ai_response['confidence'], ai_response['intent'])
        
        # Check escalation
        escalation_triggered = False
        if ai_response['escalation_needed']:
            escalation_triggered = await self.handle_escalation(session)
        
        # Send AI response to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': ai_response['response'],
                'message_type': 'ai',
                'confidence': ai_response['confidence'],
                'intent': ai_response['intent'],
                'escalation_triggered': escalation_triggered,
            }
        )
    
    async def handle_agent_message(self, message, user_id):
        """Handle agent message"""
        session = await self.get_session()
        if not session:
            return
        
        saved_message = await self.save_message(session, 'agent', message, sender_id=user_id)
        
        # Broadcast to room
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'message_type': 'agent',
                    'message_id': saved_message.id if saved_message else None,
                }
            )
            print(f"✅ Agent message broadcasted to room {self.room_group_name}")
        except Exception as e:
            print(f"❌ Error broadcasting agent message: {e}")
            import traceback
            traceback.print_exc()
    
    async def chat_message(self, event):
        """Send message to WebSocket"""
        try:
            await self.send(text_data=json.dumps({
                'message': event.get('message', ''),
                'message_type': event.get('message_type', 'ai'),
                'confidence': event.get('confidence'),
                'intent': event.get('intent'),
                'escalation_triggered': event.get('escalation_triggered', False),
                'sender_name': event.get('sender_name'),
                'sender_profile_picture': event.get('sender_profile_picture'),
                'message_id': event.get('message_id'),
            }))
            print(f"✅ WebSocket message delivered: {event.get('message_type')} message")
        except Exception as e:
            print(f"❌ Error in chat_message handler: {e}")
            import traceback
            traceback.print_exc()
    
    async def agent_connected(self, event):
        """Send agent connection notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'agent_connected',
            'agent_name': event['agent_name'],
            'agent_username': event['agent_username'],
            'message': event['message'],
            'agent_connected': True,
        }))
    
    @database_sync_to_async
    def get_session(self):
        try:
            return ChatSession.objects.get(session_id=self.session_id)
        except ChatSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def save_message(self, session, message_type, content, confidence=None, intent=None, sender_id=None):
        from django.contrib.auth.models import User
        sender = None
        if sender_id:
            try:
                sender = User.objects.get(id=sender_id)
            except User.DoesNotExist:
                pass
        
        return Message.objects.create(
            session=session,
            message_type=message_type,
            content=content,
            sender=sender,
            ai_confidence=confidence,
            intent_detected=intent,
        )
    
    @database_sync_to_async
    def handle_escalation(self, session):
        return EscalationHandler.assign_agent(session)

