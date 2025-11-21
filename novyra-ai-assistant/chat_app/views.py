"""Consolidated API Views for Chat App"""
import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from django.db.models import Q, Count, Avg, F
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import ChatSession, Message, KnowledgeBase, Agent, Analytics, UserProfile, LoginHistory, Notification, Ticket, ConversationLearning, ChatWidgetConfig, AgentChat, AgentMessage, AgentNote
from .serializers import (
    ChatSessionSerializer, ChatSessionListSerializer, MessageSerializer,
    ChatRequestSerializer, ChatResponseSerializer, KnowledgeBaseSerializer,
    AgentSerializer, AnalyticsSerializer, UserProfileSerializer,
    LoginHistorySerializer, NotificationSerializer, ChangePasswordSerializer,
    UpdateProfileSerializer
)
from .ai_engine import AIEngine
from .escalation import EscalationHandler
from .utils import (
    can_connect_to_agent, check_business_hours, scrape_website_content, create_default_faqs, check_agent_availability,
    create_ticket, save_conversation_learning, get_common_questions,
    get_business_hours_message, send_after_hours_email_notification,
    mark_message_as_read, send_ticket_email_notification,
)


class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for chat sessions"""
    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChatSessionListSerializer
        return ChatSessionSerializer
    
    def get_queryset(self):
        user = self.request.user
        # Allow unauthenticated access in debug mode for testing
        if not user.is_authenticated and settings.DEBUG:
            return ChatSession.objects.all()[:50]  # Limit for unauthenticated
        # Agents see their assigned sessions, admins see all
        if user.is_staff:
            return ChatSession.objects.all()
        return ChatSession.objects.filter(assigned_agent=user)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message in a chat session (agent or user)"""
        session = self.get_object()
        content = request.data.get('content', '')
        message_type = request.data.get('message_type', 'agent' if request.user.is_authenticated else 'user')
        
        if not content:
            return Response({'error': 'Message content is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # If agent is sending message, ensure session is assigned to them or update status
        if message_type == 'agent' and request.user.is_authenticated:
            if not session.assigned_agent:
                session.assigned_agent = request.user
                session.status = 'agent_assigned'
                session.save()
                # Update agent's current chat count
                try:
                    agent_profile = request.user.agent_profile
                    # Use update() to avoid race conditions
                    Agent.objects.filter(id=agent_profile.id).update(current_chats=F('current_chats') + 1)
                except Agent.DoesNotExist:
                    Agent.objects.create(user=request.user, current_chats=1, is_available=True, max_concurrent_chats=5)
        
        message = Message.objects.create(
            session=session,
            message_type=message_type,
            content=content,
            sender=request.user if request.user.is_authenticated else None,
        )
        
        # Update session updated_at
        session.save()
        
        # Send message via WebSocket for real-time delivery
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if channel_layer:
                room_group_name = f'chat_{session.session_id}'
                sender_name = None
                if request.user.is_authenticated:
                    sender_name = request.user.get_full_name() or request.user.username
                
                # Send via WebSocket
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'chat_message',
                        'message': content,
                        'message_type': message_type,
                        'sender_name': sender_name,
                        'sender_profile_picture': None,
                        'message_id': message.id,
                    }
                )
                print(f"✅ WebSocket message sent: {message_type} message to room {room_group_name}")
        except Exception as e:
            print(f"❌ Error sending WebSocket message: {e}")
            import traceback
            traceback.print_exc()
            # Continue even if WebSocket fails - polling will pick it up
        
        # Create notification for the other party
        if message_type == 'agent':
            # Notify customer via notification (for badge count)
            # WebSocket handles real-time delivery
            pass
        elif message_type == 'user' and session.assigned_agent:
            # Notify assigned agent
            create_notification(
                session.assigned_agent,
                'message',
                f'New message from customer',
                content[:100],
                session
            )
        
        return Response(MessageSerializer(message, context={'request': request}).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'])
    def delete_session(self, request, pk=None):
        """Delete a chat session (soft delete by setting status to closed)"""
        if not request.user.is_authenticated or not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        session = self.get_object()
        session.status = 'closed'
        session.save()
        
        # Release agent if assigned
        EscalationHandler.release_agent(session)
        
        return Response({'status': 'Session deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def close_session(self, request, pk=None):
        """Close a chat session"""
        session = self.get_object()
        session.status = 'closed'
        session.resolved_at = timezone.now()
        session.save()
        
        EscalationHandler.release_agent(session)
        return Response({'status': 'Session closed'})
    
    @action(detail=True, methods=['post'])
    def rate_session(self, request, pk=None):
        """Rate a chat session"""
        session = self.get_object()
        rating = request.data.get('rating')
        feedback = request.data.get('feedback', '')
        
        if rating and 1 <= int(rating) <= 5:
            session.rating = int(rating)
            session.feedback = feedback
            session.save()
            return Response({'status': 'Rating saved'})
        return Response({'error': 'Invalid rating'}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def chat_api(request):
    """
    Main chat API endpoint - handles user messages and AI responses
    Public endpoint (no auth required for users)
    CSRF exempt to allow embedding on external websites
    """
    try:
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        session_id = data.get('session_id') or str(uuid.uuid4())
        user_message = data.get('message')
        
        if not user_message or not user_message.strip():
            return Response({
                'error': 'Message cannot be empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get client IP from request
        user_ip = data.get('user_ip') or request.META.get('REMOTE_ADDR', '')
        
        # Get or create session
        session, created = ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user_ip': user_ip if user_ip else None,
                'user_agent': data.get('user_agent', request.META.get('HTTP_USER_AGENT', '')),
                'status': 'active',
                'customer_name': data.get('customer_name'),
                'customer_email': data.get('customer_email'),
                'customer_phone': data.get('customer_phone'),
            }
        )
        
        # Update customer info if provided
        if not created:
            if data.get('customer_name'):
                session.customer_name = data.get('customer_name')
            if data.get('customer_email'):
                session.customer_email = data.get('customer_email')
            if data.get('customer_phone'):
                session.customer_phone = data.get('customer_phone')
            session.save()
        
        # Store previous agent ID to detect new connections (before processing)
        previous_agent_id = session.assigned_agent.id if session.assigned_agent else None
        
        # Check business hours
        is_business_hours = check_business_hours()
        business_hours_message = get_business_hours_message()
        
        # Save user message
        user_msg = Message.objects.create(
            session=session,
            message_type='user',
            content=user_message.strip(),
        )
        
        # If after business hours, send email notification
        if not is_business_hours:
            send_after_hours_email_notification(session, user_message.strip())
        
        # CRITICAL: If agent is already connected, skip AI processing completely
        # Let agent and customer chat freely without AI interference
        if session.assigned_agent and previous_agent_id:
            # Agent already connected - skip AI, return empty response
            ai_response = {
                'response': '',
                'confidence': 0.0,
                'intent': 'agent_chat',
                'escalation_needed': False,
                'kb_entry': None,
                'deepseek_failed': False,
                'agent_connected': True,
                'show_connection_message': False  # Don't show connection message
            }
        else:
            # Process with AI engine - let DeepSeek AI answer questions intelligently
            ai_engine = AIEngine()
            session_context = {
                'last_intent': session.last_intent,
                'package_selected': session.package_selected,
                'ticket_suggested': session.ticket_suggested,
                'has_left_message': session.has_left_message,
            }
            ai_response = ai_engine.generate_response(user_message, session_id, is_business_hours=is_business_hours, session_context=session_context)
        
        # Check for explicit agent requests (very specific - only clear intent)
        normalized_msg = user_message.lower().strip()
        explicit_agent_keywords = [
            'i want to speak with an agent', 'i want to talk to an agent',
            'connect me to an agent', 'connect me to a human',
            'i need to speak with an agent', 'i need to talk to an agent',
            'let me speak with an agent', 'let me talk to an agent',
            'speak with an agent', 'talk to an agent', 'get an agent',
            'i want a human', 'i need a human', 'real person', 'real human agent'
        ]
        
        # Check for explicit agent requests
        wants_agent = any(keyword in normalized_msg for keyword in explicit_agent_keywords)
        
        # Also check for "speak with" or "talk to" followed by agent/human
        if not wants_agent and ('speak with' in normalized_msg or 'talk to' in normalized_msg):
            if 'agent' in normalized_msg or 'human' in normalized_msg or 'representative' in normalized_msg:
                wants_agent = True
        
        print(f"🔍 Agent request detection: message='{user_message}', wants_agent={wants_agent}, ai_escalation={ai_response.get('escalation_needed', False)}")
        
        escalation_triggered = False
        assigned_agent_name = None
        
        # Only escalate if:
        # 1. User explicitly wants agent, OR
        # 2. DeepSeek AI truly failed to answer (not just suggesting agent)
        deepseek_failed = ai_response.get('deepseek_failed', False)
        
        # CRITICAL: Only escalate if user EXPLICITLY requests OR DeepSeek truly can't answer
        # Don't escalate for general questions - let AI handle them
        # DeepSeek failure means it genuinely can't help, not just suggesting escalation
        should_escalate = wants_agent or (deepseek_failed and ai_response.get('escalation_needed', False))
        
        # If user didn't explicitly ask and DeepSeek didn't fail, don't escalate
        # Let AI have normal conversations
        if not wants_agent and not deepseek_failed:
            should_escalate = False
        
        if should_escalate and not session.assigned_agent:
            print(f"🚨 ESCALATION NEEDED - wants_agent={wants_agent}, ai_escalation={ai_response.get('escalation_needed', False)}")
            agents_available = check_agent_availability()
            print(f"🔍 AGENT CHECK: is_business_hours={is_business_hours}, agents_available={agents_available}")
            
            # Try to assign agent if available (prefer business hours, but try anyway if agents are available)
            if agents_available:
                # Try to assign agent
                escalation_triggered = EscalationHandler.assign_agent(session)
                session.refresh_from_db()
                
                # Check if agent was actually assigned (even if method returned False)
                if session.assigned_agent:
                    escalation_triggered = True  # Ensure this is set
                    assigned_agent_name = session.assigned_agent.get_full_name() or session.assigned_agent.username
                    print(f"✅ Agent assigned successfully: {assigned_agent_name}")
                    
                    # Create notification for assigned agent with sound
                    create_notification(
                        session.assigned_agent,
                        'escalation',
                        '🔔 New Customer Session',
                        f'Customer {session.customer_name or "Guest"} needs assistance. Session: {session.session_id[:8]}',
                        session
                    )
                else:
                    print(f"⚠️ Agent assignment failed - no agent assigned despite availability check")
                    escalation_triggered = False
            else:
                print(f"⚠️ No agents available for escalation")
                escalation_triggered = False
        
        # If agent was successfully assigned, handle it appropriately
        # Check both escalation_triggered flag AND actual assignment
        if (escalation_triggered or session.assigned_agent) and session.assigned_agent:
            # Check if this is a NEW connection (agent just assigned in this request)
            was_already_connected = (session.assigned_agent.id == previous_agent_id) if previous_agent_id else False
            
            if not was_already_connected:
                # This is a NEW connection - show connection message ONCE
                if wants_agent:
                    # User explicitly asked for agent - show connection message
                    ai_response['response'] = f"✅ Great! I've connected you with {assigned_agent_name}. They'll be with you shortly.\n\n💬 You can start chatting now - your agent will see your messages!"
                else:
                    # DeepSeek failed - show subtle connection message
                    ai_response['response'] = f"I've connected you with {assigned_agent_name} who can better assist you. You can start chatting now!"
                
                # Mark that connection message was shown
                ai_response['agent_connected'] = True
                ai_response['show_connection_message'] = True  # Flag to show message
            else:
                # Agent already connected - NO AI responses, NO connection messages
                # Let agent and customer chat freely without any AI interference
                ai_response['response'] = ""  # Completely clear - let them chat freely
                ai_response['agent_connected'] = True
                ai_response['show_connection_message'] = False  # Don't show connection message again
            
            ai_response['escalation_needed'] = False
            
            # Store current agent ID for next check (use previous_agent_id variable)
            previous_agent_id = session.assigned_agent.id
            
            # Send WebSocket notification about agent connection
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                
                channel_layer = get_channel_layer()
                if channel_layer:
                    room_group_name = f'chat_{session.session_id}'
                    async_to_sync(channel_layer.group_send)(
                        room_group_name,
                        {
                            'type': 'agent_connected',
                            'agent_name': assigned_agent_name,
                            'agent_username': session.assigned_agent.username,
                            'message': ai_response['response'],
                        }
                    )
            except Exception as e:
                print(f"Error sending agent connection WebSocket: {e}")
        elif should_escalate and not escalation_triggered and not session.assigned_agent:
            # User wants agent or AI says to escalate, but couldn't connect - handle based on reason
            # Only override AI response if it's a clear agent request and we need to explain the situation
            if wants_agent:  # Only override if user explicitly asked for agent
                if not is_business_hours:
                    business_hours_message = get_business_hours_message()
                    if session.has_left_message:
                        ai_response['response'] = f"{business_hours_message or '⏰ We\'re currently closed. Our business hours are Monday to Saturday, 9:00 AM to 6:00 PM (WAT).'}\n\n✅ I've received your request to speak with an agent. Our agents will reach out to you via email as soon as we're open.\n\nWhile you wait, feel free to explore:\n• 💰 Pricing Information\n• ❓ Frequently Asked Questions"
                    else:
                        session.has_left_message = True
                        session.save()
                        ai_response['response'] = business_hours_message or "⏰ We're currently closed. Our business hours are Monday to Saturday, 9:00 AM to 6:00 PM (WAT).\n\n📧 I've noted your request to speak with an agent. Our agents will reach out to you via email as soon as we're open. Please leave your message and we'll get back to you during business hours!"
                    ai_response['quick_actions'] = ['pricing', 'faqs']
                else:
                    # Business hours but no agents available
                    session.status = 'waiting_agent'
                    session.save()
                    if session.has_left_message:
                        ai_response['response'] = f"Thank you, {session.customer_name or 'there'}! I've received your request to speak with an agent. All agents are currently busy, but we'll connect you as soon as one becomes available.\n\nWhile you wait:\n• 💰 Pricing Information\n• ❓ Frequently Asked Questions"
                        ai_response['quick_actions'] = ['pricing', 'faqs', 'contact']
                    else:
                        session.has_left_message = True
                        session.save()
                        ai_response['response'] = "Thank you for reaching out! I understand you'd like to speak with an agent. All our agents are currently busy, but your chat is in queue and an agent will be with you shortly. Please leave your message below."
                        ai_response['quick_actions'] = ['pricing', 'faqs']
            # If AI said to escalate but user didn't explicitly ask, keep AI's response (it will mention connecting)
        
        # Update session context
        session.last_intent = ai_response.get('intent')
        session.save()
        
        # Check if user wants to create a ticket
        ticket_keywords = ['create ticket', 'yes create', 'create a ticket', 'make a ticket', 'support ticket']
        wants_ticket = any(keyword in user_message.lower() for keyword in ticket_keywords)
        
        if wants_ticket and not session.ticket_suggested:
            # Auto-create ticket if user explicitly requests it
            from .utils import create_ticket
            from .models import Message as MessageModel
            last_user_msg = MessageModel.objects.filter(session=session, message_type='user').order_by('-created_at').first()
            description = last_user_msg.content if last_user_msg else user_message
            
            ticket = create_ticket(session, 'Support Request', description, 'medium')
            session.ticket_suggested = True
            session.save()
            
            ai_response['response'] = f"✅ Perfect! I've created support ticket #{ticket.ticket_number} for you.\n\n"
            ai_response['response'] += "Our team will review your ticket and get back to you via email. You'll receive updates on the progress.\n\n"
            ai_response['response'] += "Is there anything else I can help you with?"
            ai_response['ticket_created'] = True
            ai_response['ticket_number'] = ticket.ticket_number
        
        # REMOVED: Duplicate escalation logic that was blocking normal AI conversations
        # Escalation is already handled above (lines 288-318) based on:
        # 1. User explicitly requesting agent, OR
        # 2. DeepSeek truly failing to answer
        # This allows AI to have normal conversations without unnecessary escalations
        
        # Save AI response only if there's a response
        # CRITICAL: Don't save AI responses when agent is already connected (let them chat freely)
        # Only save if:
        # 1. No agent is assigned, OR
        # 2. Agent was just connected (new connection - show connection message once)
        if ai_response['response'] and ai_response['response'].strip():
            # Check if agent is already connected (not a new connection)
            was_already_connected = (session.assigned_agent and session.assigned_agent.id == previous_agent_id) if previous_agent_id else False
            
            if not was_already_connected:
                # No agent or new connection - save AI response
                ai_msg = Message.objects.create(
                    session=session,
                    message_type='ai',
                    content=ai_response['response'],
                    ai_confidence=ai_response['confidence'],
                    intent_detected=ai_response['intent'],
                )
            # If agent already connected, don't save AI response - let them chat freely
        
        # Save conversation for ML learning
        save_conversation_learning(
            session=session,
            user_message=user_message,
            ai_response=ai_response['response'],
            intent=ai_response['intent'],
            confidence=ai_response['confidence'],
            escalated=escalation_triggered
        )
        
        # Notify assigned agent about new message
        if session.assigned_agent:
            create_notification(
                session.assigned_agent,
                'message',
                f'New message from customer',
                user_message[:100],
                session
            )
        elif not session.assigned_agent:
            # Notify admins about new message (if not assigned to agent)
            from django.contrib.auth.models import User
            admins = User.objects.filter(is_staff=True, is_active=True)
            customer_name = session.customer_name or data.get('customer_name', 'Customer')
            for admin in admins:
                create_notification(
                    admin,
                    'message',
                    f'New message from {customer_name}',
                    user_message[:100],
                    session
                )
        
        # Get agent profile picture URL if agent is assigned
        assigned_agent_profile_picture = None
        if session.assigned_agent:
            try:
                profile = session.assigned_agent.user_profile
                if profile.profile_picture:
                    assigned_agent_profile_picture = request.build_absolute_uri(profile.profile_picture.url)
            except UserProfile.DoesNotExist:
                pass
        
        # Prepare response
        response_data = {
            'session_id': session.session_id,
            'message': ai_response['response'],
            'message_type': 'ai',
            'ai_confidence': ai_response['confidence'],
            'intent_detected': ai_response['intent'],
            'status': session.status,
            'escalation_triggered': escalation_triggered,
            'agent_available': check_agent_availability(),
            'business_hours': is_business_hours,
            'business_hours_message': business_hours_message if wants_agent else None,
            'assigned_agent': session.assigned_agent.username if session.assigned_agent else None,
            'assigned_agent_name': assigned_agent_name or (f"{session.assigned_agent.first_name} {session.assigned_agent.last_name}".strip() if session.assigned_agent else None),
            'assigned_agent_profile_picture': assigned_agent_profile_picture,
            'quick_actions': ai_response.get('quick_actions', []),  # Add quick action buttons
            'packages': ai_response.get('kb_entry', {}).get('packages', []) if ai_response.get('intent') == 'pricing' else [],
            'ticket_created': ai_response.get('ticket_created', False),
            'ticket_number': ai_response.get('ticket_number', None),
            'agent_connected': ai_response.get('agent_connected', False),
            'show_connection_message': ai_response.get('show_connection_message', False),  # Flag for connection message
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in chat_api: {error_details}")  # Log for debugging
        return Response({
            'error': 'An error occurred processing your message',
            'details': str(e) if settings.DEBUG else 'Please try again later'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_session_messages(request, session_id):
    """Get all messages for a session"""
    try:
        session = ChatSession.objects.get(session_id=session_id)
        # Exclude system messages for regular users (they're for internal tracking)
        # Only show system messages to authenticated staff users
        if request.user.is_authenticated and request.user.is_staff:
            messages = session.messages.all().order_by('created_at')
            # Mark user messages as read when agent views them
            if request.user.is_staff:
                unread_user_messages = messages.filter(message_type='user', is_read=False)
                for message in unread_user_messages:
                    mark_message_as_read(message, request.user)
        else:
            messages = session.messages.exclude(message_type='system').order_by('created_at')
            # Mark agent messages as read when user views them
            if session.assigned_agent:
                unread_agent_messages = messages.filter(message_type='agent', is_read=False)
                # For users, we mark as read by the assigned agent (since users don't have accounts)
                # In a real implementation, you might want to track read status differently for anonymous users
                pass  # Skip auto-marking for anonymous users
        
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response({'messages': serializer.data})
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_message_api(request, message_id):
    """Delete a message (only agents/admins can delete)"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from .models import Message
        message = Message.objects.get(id=message_id)
        message.delete()
        return Response({'status': 'Message deleted'}, status=status.HTTP_200_OK)
    except Message.DoesNotExist:
        return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_message_read_api(request, message_id):
    """Mark a message as read"""
    try:
        from .models import Message
        message = Message.objects.get(id=message_id)
        mark_message_as_read(message, request.user)
        return Response({'status': 'Message marked as read'}, status=status.HTTP_200_OK)
    except Message.DoesNotExist:
        return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ticket_follow_up_api(request, ticket_id):
    """Add follow-up notes and schedule follow-up for a ticket"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from .models import Ticket
        from django.utils.dateparse import parse_datetime
        ticket = Ticket.objects.get(id=ticket_id)
        
        follow_up_notes = request.data.get('follow_up_notes', '')
        follow_up_date = request.data.get('follow_up_date', None)
        
        if follow_up_notes:
            ticket.follow_up_notes = follow_up_notes
        
        if follow_up_date:
            try:
                follow_up_date = parse_datetime(follow_up_date)
                if follow_up_date:
                    ticket.follow_up_date = follow_up_date
            except (ValueError, TypeError):
                return Response({'error': 'Invalid follow-up date format'}, status=status.HTTP_400_BAD_REQUEST)
        
        ticket.follow_up_by = request.user
        ticket.save()
        
        # Send email notification to customer if needed
        if request.data.get('notify_customer', False):
            send_ticket_email_notification(ticket, ticket.session)
        
        return Response({
            'status': 'Follow-up updated',
            'ticket_id': ticket.id,
            'follow_up_notes': ticket.follow_up_notes,
            'follow_up_date': ticket.follow_up_date,
        }, status=status.HTTP_200_OK)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def upload_file(request):
    """Upload a file attachment for a chat message
    CSRF exempt to allow embedding on external websites
    """
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Session ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create session
        session, created = ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={'status': 'active'}
        )
        
        # Determine attachment type
        import re
        message_type_param = request.data.get('message_type', 'user')
        content_type = file.content_type or ''
        file_name_lower = file.name.lower() if file.name else ''
        
        # Check if it's a voice message
        is_voice = (message_type_param == 'voice' or 
                   'audio' in content_type or 
                   any(ext in file_name_lower for ext in ['.webm', '.mp3', '.ogg', '.wav', '.m4a']))
        
        if is_voice:
            attachment_type = 'voice'
            content = '🎤 Voice message'
        elif 'image' in content_type:
            attachment_type = 'image'
            content = f'📎 {file.name}'
        elif 'pdf' in content_type or 'document' in content_type:
            attachment_type = 'document'
            content = f'📎 {file.name}'
        elif 'video' in content_type:
            attachment_type = 'video'
            content = f'📎 {file.name}'
        else:
            attachment_type = 'document'
            content = f'📎 {file.name}'
        
        # Create message with attachment
        message = Message.objects.create(
            session=session,
            message_type='user',
            content=content,
            attachment=file,
            attachment_type=attachment_type
        )
        
        serializer = MessageSerializer(message, context={'request': request})
        return Response({
            'message': f'File {file.name} uploaded successfully',
            'attachment_url': serializer.data.get('attachment_url'),
            'attachment_type': attachment_type
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': 'Error uploading file',
            'details': str(e) if settings.DEBUG else 'Please try again'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """ViewSet for knowledge base management"""
    queryset = KnowledgeBase.objects.filter(is_active=True)
    serializer_class = KnowledgeBaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return KnowledgeBase.objects.all()
        return KnowledgeBase.objects.filter(is_active=True)


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for agent management"""
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def set_availability(self, request, pk=None):
        """Set agent availability"""
        agent = self.get_object()
        is_available = request.data.get('is_available', True)
        agent.is_available = is_available
        agent.save()
        return Response({'status': f'Availability set to {is_available}'})


@api_view(['GET'])
@permission_classes([AllowAny])
def faqs_api(request):
    """Get all FAQ entries"""
    faqs = KnowledgeBase.objects.filter(category='faq', is_active=True).order_by('-priority', 'title')
    serializer = KnowledgeBaseSerializer(faqs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def services_api(request):
    """Get all service entries"""
    services = KnowledgeBase.objects.filter(category='service', is_active=True).order_by('-priority', 'title')
    serializer = KnowledgeBaseSerializer(services, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def pricing_api(request):
    """Get pricing information with interactive packages"""
    from .ai_engine import AIEngine
    ai_engine = AIEngine()
    return Response({
        'pricing': ai_engine.pricing_info['content'],
        'packages': ai_engine.pricing_info.get('packages', [
            {'name': 'Basic', 'price': '₦30,000/month', 'id': 'basic', 'features': [
                'Social Media Account Setup (up to 3 platforms)',
                '3 Branded Posts/Month (Graphics + Captions)',
                'Ad Account Setup (Facebook/Instagram)',
                'Basic Page Set-up (Bio, Highlights, CTA Button)',
                '1 Promotional Video'
            ]},
            {'name': 'Premium', 'price': '₦45,000/month', 'id': 'premium', 'features': [
                'Social Media Account Setup (up to 3 platforms)',
                '6 Branded Posts/Month (Graphics + Captions)',
                'Ad Account Setup (Facebook/Instagram)',
                'Basic Page Set-up (Bio, Highlights, CTA Button)',
                'Weekly Performance Check-in',
                '3 Promotional Videos'
            ]},
            {'name': 'Elite', 'price': '₦65,000/month', 'id': 'elite', 'features': [
                'Social Media Account Setup (up to 3 platforms)',
                '8 Branded Posts/Month (Graphics + Captions)',
                '2 Ad Account Setup (Facebook/Instagram)',
                'Basic Page Set-up (Bio, Highlights, CTA Button)',
                'Weekly Performance Check-in',
                '5 Promotional Videos',
                'Full Social Media Management'
            ]},
        ])
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def services_detail_api(request):
    """Get detailed services information from AI engine"""
    from .ai_engine import AIEngine
    ai_engine = AIEngine()
    services_list = []
    for service_key, service_data in ai_engine.novyra_services.items():
        services_list.append({
            'key': service_key,
            'title': service_key.replace('_', ' ').title(),
            'content': service_data['content'],
            'keywords': service_data['keywords']
        })
    return Response({
        'services': services_list
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def agent_availability_api(request):
    """Check agent availability and business hours"""
    try:
        is_available = check_agent_availability()
        is_business_hours = check_business_hours()
        business_hours_message = get_business_hours_message()
        
        # Get available agents count
        available_agents_count = 0
        try:
            available_agents_count = Agent.objects.filter(
                is_available=True,
                user__is_active=True,
                current_chats__lt=F('max_concurrent_chats')
            ).count()
        except Exception:
            pass
        
        return Response({
            'available': is_available,
            'business_hours': is_business_hours,
            'can_connect': is_available and is_business_hours,
            'business_hours_message': business_hours_message,
            'available_agents_count': available_agents_count,
            'agents_available': is_available  # For backward compatibility
        })
    except Exception as e:
        return Response({
            'available': False,
            'business_hours': False,
            'can_connect': False,
            'error': str(e) if settings.DEBUG else 'Error checking availability'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def common_questions_api(request):
    """Get common questions for option buttons"""
    questions = get_common_questions()
    return Response(questions)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_ticket_api(request):
    """Create a support ticket"""
    from .utils import create_ticket
    from .models import ChatSession, Message
    
    session_id = request.data.get('session_id')
    title = request.data.get('title', 'Support Request')
    description = request.data.get('description', '')
    priority = request.data.get('priority', 'medium')
    
    if not session_id:
        return Response({'error': 'Session ID required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        session = ChatSession.objects.get(session_id=session_id)
        
        # If no description, use the last user message
        if not description:
            last_message = Message.objects.filter(session=session, message_type='user').order_by('-created_at').first()
            if last_message:
                description = last_message.content
        
        ticket = create_ticket(session, title, description, priority)
        
        # Mark ticket as suggested
        session.ticket_suggested = True
        session.save()
        
        # Create confirmation message
        confirmation_msg = f"✅ Perfect! I've created support ticket #{ticket.ticket_number} for you.\n\n"
        confirmation_msg += f"**Title:** {ticket.title}\n"
        confirmation_msg += f"**Priority:** {ticket.get_priority_display()}\n\n"
        confirmation_msg += "Our team will review your ticket and get back to you via email. You'll receive updates on the progress.\n\n"
        confirmation_msg += "Is there anything else I can help you with?"
        
        return Response({
            'ticket_number': ticket.ticket_number,
            'title': ticket.title,
            'status': ticket.status,
            'priority': ticket.priority,
            'confirmation_message': confirmation_msg,
        }, status=status.HTTP_201_CREATED)
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def widget_config_api(request):
    """Get widget configuration including bot name and profile image"""
    config = ChatWidgetConfig.objects.filter(is_active=True).first()
    if not config:
        # Create default config
        config = ChatWidgetConfig.objects.create(
            name='Default Widget',
            bot_name='Ariho',
            button_color='#0006B1',
            button_position='bottom-right',
            widget_width=420,
            widget_height=600
        )
    
    bot_profile_image_url = None
    if config.bot_profile_image:
        bot_profile_image_url = request.build_absolute_uri(config.bot_profile_image.url)
    
    return Response({
        'bot_name': config.bot_name,
        'bot_profile_image': bot_profile_image_url,
        'button_color': config.button_color,
        'button_position': config.button_position,
        'widget_width': config.widget_width,
        'widget_height': config.widget_height,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_widget_config_api(request):
    """Update widget configuration including bot name and profile image (requires authentication)"""
    config = ChatWidgetConfig.objects.filter(is_active=True).first()
    if not config:
        config = ChatWidgetConfig.objects.create(
            name='Default Widget',
            bot_name='Ariho',
            button_color='#0006B1',
            button_position='bottom-right',
            widget_width=420,
            widget_height=600
        )
    
    # Update bot name
    if 'bot_name' in request.data:
        config.bot_name = request.data['bot_name']
    
    # Update bot profile image
    if 'bot_profile_image' in request.FILES:
        config.bot_profile_image = request.FILES['bot_profile_image']
    
    config.save()
    
    bot_profile_image_url = None
    if config.bot_profile_image:
        bot_profile_image_url = request.build_absolute_uri(config.bot_profile_image.url)
    
    return Response({
        'bot_name': config.bot_name,
        'bot_profile_image': bot_profile_image_url,
        'message': 'Bot configuration updated successfully'
    })


# Agent Chat API Endpoints
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def agent_chats_api(request):
    """List or create agent-to-agent chats"""
    if request.method == 'GET':
        # Get all chats where current user is a participant
        chats = AgentChat.objects.filter(participants=request.user, is_active=True)
        serializer = AgentChatSerializer(chats, many=True, context={'request': request})
        return Response({'results': serializer.data})
    
    elif request.method == 'POST':
        # Create new agent chat
        participant_usernames = request.data.get('participant_usernames', [])
        title = request.data.get('title', None)
        
        # Add current user to participants
        participants = [request.user]
        for username in participant_usernames:
            try:
                user = User.objects.get(username=username)
                if user != request.user:
                    participants.append(user)
            except User.DoesNotExist:
                return Response({'error': f'User {username} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Create chat
        chat = AgentChat.objects.create(title=title or None)
        chat.participants.set(participants)
        
        serializer = AgentChatSerializer(chat, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def agent_chat_messages_api(request, chat_id):
    """Get or send messages in an agent chat"""
    try:
        chat = AgentChat.objects.get(id=chat_id, participants=request.user, is_active=True)
    except AgentChat.DoesNotExist:
        return Response({'error': 'Chat not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        messages = chat.messages.all()
        serializer = AgentMessageSerializer(messages, many=True, context={'request': request})
        return Response({'messages': serializer.data})
    
    elif request.method == 'POST':
        content = request.data.get('content', '')
        if not content:
            return Response({'error': 'Message content is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        message = AgentMessage.objects.create(
            chat=chat,
            sender=request.user,
            content=content
        )
        
        # Mark as read for sender
        message.is_read = True
        message.save()
        
        # Update chat updated_at
        chat.save()
        
        serializer = AgentMessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_chat_add_participant_api(request, chat_id):
    """Add a participant to an agent chat"""
    try:
        chat = AgentChat.objects.get(id=chat_id, participants=request.user, is_active=True)
    except AgentChat.DoesNotExist:
        return Response({'error': 'Chat not found'}, status=status.HTTP_404_NOT_FOUND)
    
    username = request.data.get('username', '')
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(username=username)
        chat.participants.add(user)
        chat.save()
        return Response({'message': 'Participant added successfully'})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def agent_notes_api(request, session_id):
    """Get or create agent notes for a session"""
    try:
        session = ChatSession.objects.get(session_id=session_id)
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Get notes visible to current user (non-private or owned by user)
        notes = AgentNote.objects.filter(
            session=session
        ).filter(
            Q(is_private=False) | Q(agent=request.user)
        )
        serializer = AgentNoteSerializer(notes, many=True)
        return Response({'notes': serializer.data})
    
    elif request.method == 'POST':
        note_text = request.data.get('note', '')
        is_private = request.data.get('is_private', False)
        
        if not note_text:
            return Response({'error': 'Note content is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        note = AgentNote.objects.create(
            session=session,
            agent=request.user,
            note=note_text,
            is_private=is_private
        )
        
        serializer = AgentNoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def embed_widget(request, config_id=None):
    """Serve the embeddable chat widget"""
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    
    # Get widget config (use default if not specified)
    if config_id:
        try:
            config = ChatWidgetConfig.objects.get(id=config_id, is_active=True)
        except ChatWidgetConfig.DoesNotExist:
            config = ChatWidgetConfig.objects.filter(is_active=True).first()
    else:
        config = ChatWidgetConfig.objects.filter(is_active=True).first()
    
    if not config:
        # Create default config
        config = ChatWidgetConfig.objects.create(
            name='Default Widget',
            bot_name='Ariho',
            button_color='#0006B1',
            button_position='bottom-right',
            widget_width=420,
            widget_height=600
        )
    
    # Determine position CSS
    position_map = {
        'bottom-right': 'bottom: 20px; right: 20px;',
        'bottom-left': 'bottom: 20px; left: 20px;',
        'top-right': 'top: 20px; right: 20px;',
        'top-left': 'top: 20px; left: 20px;',
    }
    position_css = position_map.get(config.button_position, 'bottom: 20px; right: 20px;')
    
    # Get API base URL
    api_base_url = request.build_absolute_uri('/').rstrip('/')
    
    context = {
        'bot_name': config.bot_name,
        'button_color': config.button_color,
        'button_position': config.button_position,
        'widget_width': config.widget_width,
        'widget_height': config.widget_height,
        'position_css': position_css,
        'api_base_url': api_base_url,
        'is_embedded': True,  # Mark as embedded
    }
    
    return HttpResponse(render_to_string('chat_interface.html', context), content_type='text/html')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def embed_code(request, config_id=None):
    """Get embed code for a widget configuration"""
    # Check if user is authenticated (works with both session and JWT)
    if not request.user or not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get widget config
    if config_id:
        try:
            config = ChatWidgetConfig.objects.get(id=config_id)
        except ChatWidgetConfig.DoesNotExist:
            return Response({'error': 'Widget config not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        config = ChatWidgetConfig.objects.filter(is_active=True).first()
        if not config:
            config = ChatWidgetConfig.objects.create(
                name='Default Widget',
                button_color='#0006B1',
                button_position='bottom-right',
                widget_width=420,
                widget_height=600
            )
    
    # Generate embed code
    # IMPORTANT: For embed widgets to work on external websites, we need the actual server domain
    # not localhost (127.0.0.1). Set EMBED_BASE_URL in your .env file with your actual domain.
    
    # Get the base URL - prefer settings (EMBED_BASE_URL), then request host
    embed_base_url = getattr(settings, 'EMBED_BASE_URL', None)
    
    if embed_base_url:
        # Use configured embed base URL
        embed_base_url = embed_base_url.rstrip('/')
    else:
        # Try to get from request host
        host = request.get_host()
        scheme = 'https' if request.is_secure() else 'http'
        embed_base_url = f"{scheme}://{host}"
        
        # Check if it's localhost - if so, try to get from forwarded headers (for reverse proxy)
        if '127.0.0.1' in embed_base_url or 'localhost' in embed_base_url:
            forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST')
            forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO', 'https')
            if forwarded_host:
                embed_base_url = f"{forwarded_proto}://{forwarded_host.split(',')[0].strip()}"
            else:
                # Still localhost - this will not work on external websites!
                # We'll use it but include a warning in the response
                pass
    
    embed_url = f"{embed_base_url}/api/embed/{config.id}/?embed=true" if config_id else f"{embed_base_url}/api/embed/?embed=true"
    
    # Check if we're using localhost and warn
    is_localhost = '127.0.0.1' in embed_base_url or ('localhost' in embed_base_url and 'localhost.com' not in embed_base_url)
    
    # Generate working embed code - simple and clean
    # Calculate position styles
    position_styles = {
        'bottom-right': {'bottom': '25px', 'right': '25px'},
        'bottom-left': {'bottom': '25px', 'left': '25px'},
        'top-right': {'top': '25px', 'right': '25px'},
        'top-left': {'top': '25px', 'left': '25px'}
    }
    pos = position_styles.get(config.button_position, position_styles['bottom-right'])
    pos_css = '; '.join([f"{k}: {v}" for k, v in pos.items()])
    
    embed_code_html = f'''<!-- Novyra Chat Widget -->
<!-- Copy and paste this code before the closing </body> tag on your website -->
<script>
(function() {{
    if (window.novyraWidgetLoaded) return;
    window.novyraWidgetLoaded = true;
    
    var embedUrl = '{embed_url}';
    var buttonColor = '{config.button_color}';
    var widgetWidth = {config.widget_width};
    var widgetHeight = {config.widget_height};
    var posStyle = '{pos_css}';
    
    // Create floating button
    var btn = document.createElement('button');
    btn.id = 'novyra-chat-btn';
    btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" fill="white"/></svg>';
    btn.style.cssText = 'position:fixed;width:60px;height:60px;border-radius:50%;background:' + buttonColor + ';color:white;border:2px solid #CFB53B;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,0.3);z-index:999999;display:flex;align-items:center;justify-content:center;transition:all 0.3s;' + posStyle + ';';
    btn.onmouseover = function() {{ this.style.transform = 'scale(1.1)'; }};
    btn.onmouseout = function() {{ this.style.transform = 'scale(1)'; }};
    
    // Create widget container
    var container = document.createElement('div');
    container.id = 'novyra-widget-container';
    container.style.cssText = 'position:fixed;width:' + widgetWidth + 'px;height:' + widgetHeight + 'px;max-width:calc(100vw - 40px);max-height:calc(100vh - 40px);z-index:1000000;display:none;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,0.3);overflow:hidden;' + posStyle + ';';
    
    var iframe = document.createElement('iframe');
    iframe.src = embedUrl;
    iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;';
    iframe.allow = 'microphone; camera';
    iframe.setAttribute('frameborder', '0');
    container.appendChild(iframe);
    
    // Toggle function
    var isOpen = false;
    btn.onclick = function() {{
        isOpen = !isOpen;
        container.style.display = isOpen ? 'block' : 'none';
        btn.style.display = isOpen ? 'none' : 'flex';
    }};
    
    // Listen for close messages from iframe
    window.addEventListener('message', function(e) {{
        if (e.data && (e.data === 'novyra-close-widget' || e.data.type === 'novyra-close-widget')) {{
            isOpen = false;
            container.style.display = 'none';
            btn.style.display = 'flex';
        }}
    }});
    
    // Append to page
    document.body.appendChild(btn);
    document.body.appendChild(container);
    
    // Mobile responsive
    function adjustMobile() {{
        if (window.innerWidth <= 480) {{
            container.style.width = 'calc(100vw - 20px)';
            container.style.height = 'calc(100vh - 20px)';
            container.style.bottom = '10px';
            container.style.right = '10px';
            container.style.left = '10px';
            container.style.top = '10px';
        }} else {{
            container.style.width = widgetWidth + 'px';
            container.style.height = widgetHeight + 'px';
            var styles = posStyle.split(';');
            for (var i = 0; i < styles.length; i++) {{
                var style = styles[i].trim();
                if (style) {{
                    var parts = style.split(':');
                    if (parts.length === 2) {{
                        container.style[parts[0].trim()] = parts[1].trim();
                    }}
                }}
            }}
        }}
    }}
    window.addEventListener('resize', adjustMobile);
    adjustMobile();
}})();
</script>'''
    
    response_data = {
        'embed_code': embed_code_html,
        'config': {
            'id': config.id,
            'name': config.name,
            'button_color': config.button_color,
            'button_position': config.button_position,
            'widget_width': config.widget_width,
            'widget_height': config.widget_height,
        },
        'embed_url': embed_url,
    }
    
    # Add warning if using localhost (won't work on external websites)
    if is_localhost:
        response_data['warning'] = (
            '⚠️ WARNING: Embed code is using localhost (127.0.0.1). '
            'This will NOT work on external websites!\n\n'
            'To fix this, set EMBED_BASE_URL in your .env file with your actual server domain.\n'
            'Example: EMBED_BASE_URL=https://yourdomain.com\n\n'
            'Then restart your server and regenerate the embed code.'
        )
        response_data['is_localhost'] = True
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([AllowAny] if settings.DEBUG else [IsAuthenticated])
def analytics_api(request):
    """Get analytics data with real-time metrics"""
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    # Calculate analytics
    sessions = ChatSession.objects.all()
    if date_from:
        sessions = sessions.filter(created_at__gte=date_from)
    if date_to:
        sessions = sessions.filter(created_at__lte=date_to)
    
    total_sessions = sessions.count()
    ai_resolved = sessions.filter(status='resolved', assigned_agent__isnull=True).count()
    agent_resolved = sessions.filter(status='resolved', assigned_agent__isnull=False).count()
    escalation_count = sessions.filter(status__in=['waiting_agent', 'agent_assigned']).count()
    active_sessions = sessions.filter(status__in=['active', 'waiting_agent', 'agent_assigned']).count()
    
    # Calculate average rating
    rated_sessions = sessions.exclude(rating__isnull=True)
    avg_rating = rated_sessions.aggregate(Avg('rating'))['rating__avg'] or 0.0
    
    # Calculate daily activity (last 7 days)
    from datetime import timedelta
    daily_activity = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        day_sessions = sessions.filter(created_at__date=date).count()
        daily_activity.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%a'),
            'count': day_sessions
        })
    
    # Monthly performance (last 6 months)
    monthly_performance = []
    for i in range(5, -1, -1):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        month_sessions = sessions.filter(created_at__gte=month_start, created_at__lt=month_end).count()
        monthly_performance.append({
            'month': month_start.strftime('%b'),
            'count': month_sessions
        })
    
    # Peak hours (by hour of day)
    from django.db.models import Count
    from django.db.models.functions import ExtractHour
    peak_hours_data = []
    for hour in range(24):
        hour_sessions = sessions.filter(created_at__hour=hour).count()
        peak_hours_data.append({
            'hour': f'{hour:02d}:00',
            'count': hour_sessions
        })
    
    # Status distribution
    status_distribution = {}
    for status_code, status_name in ChatSession.STATUS_CHOICES:
        count = sessions.filter(status=status_code).count()
        if count > 0:
            status_distribution[status_name] = count
    
    # Calculate percentage changes (compare with previous period)
    if date_from or date_to:
        # For date range, compare with same period before
        prev_sessions = ChatSession.objects.all()
        if date_from:
            from_date = timezone.datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            prev_from = from_date - (timezone.now() - from_date)
            prev_sessions = prev_sessions.filter(created_at__gte=prev_from)
        if date_to:
            to_date = timezone.datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            prev_to = to_date - (timezone.now() - to_date)
            prev_sessions = prev_sessions.filter(created_at__lte=prev_to)
        
        prev_total = prev_sessions.count()
        prev_ai_resolved = prev_sessions.filter(status='resolved', assigned_agent__isnull=True).count()
    else:
        # Compare with last 7 days vs previous 7 days
        week_ago = timezone.now() - timedelta(days=7)
        two_weeks_ago = timezone.now() - timedelta(days=14)
        prev_sessions = ChatSession.objects.filter(created_at__gte=two_weeks_ago, created_at__lt=week_ago)
        prev_total = prev_sessions.count()
        prev_ai_resolved = prev_sessions.filter(status='resolved', assigned_agent__isnull=True).count()
    
    total_change = ((total_sessions - prev_total) / prev_total * 100) if prev_total > 0 else 0
    ai_resolved_change = ((ai_resolved - prev_ai_resolved) / prev_ai_resolved * 100) if prev_ai_resolved > 0 else 0
    
    analytics_data = {
        'total_sessions': total_sessions,
        'ai_resolved': ai_resolved,
        'agent_resolved': agent_resolved,
        'escalation_count': escalation_count,
        'active_sessions': active_sessions,
        'average_rating': round(avg_rating, 2),
        'resolution_rate': round((ai_resolved + agent_resolved) / total_sessions * 100, 2) if total_sessions > 0 else 0,
        'daily_activity': daily_activity,
        'monthly_performance': monthly_performance,
        'peak_hours': peak_hours_data,
        'status_distribution': status_distribution,
        'total_sessions_change': round(total_change, 1),
        'ai_resolved_change': round(ai_resolved_change, 1),
    }
    
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    """API root endpoint - provides API information"""
    return JsonResponse({
        'name': 'Novyra AI Assistant API',
        'version': '1.0.0',
        'description': 'AI-powered chat assistant system for Novyra',
        'endpoints': {
            'chat': '/api/chat/',
            'admin': '/admin/',
            'dashboard': '/dashboard/',
            'api_docs': '/api/',
            'authentication': {
                'login': '/api/auth/login/',
                'refresh': '/api/auth/refresh/',
            },
            'sessions': '/api/sessions/',
            'agents': '/api/agents/',
            'knowledge_base': '/api/knowledge-base/',
            'analytics': '/api/analytics/',
        },
        'documentation': 'See API_DOCUMENTATION.md for detailed API documentation',
    })


def chat_interface(request):
    """Render chat test interface"""
    return render(request, 'chat_interface.html')


def login_view(request):
    """Render login page"""
    if request.user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect': '/dashboard/'})
        return redirect('admin-dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'redirect': '/dashboard/'})
            return redirect('admin-dashboard')
        else:
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid username or password'}, status=400)
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    
    return render(request, 'login.html')


def logout_view(request):
    """Handle logout"""
    logout(request)
    return redirect('login')


@login_required(login_url='/login/')
def admin_dashboard(request):
    """Render admin dashboard - requires authentication and staff status"""
    if not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'admin_dashboard.html')


# Profile Management Views
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update user profile"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = UpdateProfileSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            # Update user fields
            if 'first_name' in data:
                request.user.first_name = data['first_name']
            if 'last_name' in data:
                request.user.last_name = data['last_name']
            if 'email' in data:
                request.user.email = data['email']
            request.user.save()
            
            # Update profile fields
            if 'phone_number' in data:
                profile.phone_number = data['phone_number']
            if 'bio' in data:
                profile.bio = data['bio']
            profile.save()
            
            return Response(UserProfileSerializer(profile, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload profile picture"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if 'profile_picture' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    profile.profile_picture = request.FILES['profile_picture']
    profile.save()
    
    serializer = UserProfileSerializer(profile, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password"""
    serializer = ChangePasswordSerializer(data=request.data)
    if serializer.is_valid():
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'Incorrect old password'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password changed successfully'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_history(request):
    """Get user login history"""
    history = LoginHistory.objects.filter(user=request.user)[:50]
    serializer = LoginHistorySerializer(history, many=True)
    return Response(serializer.data)


# Notification Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications(request):
    """Get user notifications"""
    notifications_list = Notification.objects.filter(user=request.user)[:50]
    serializer = NotificationSerializer(notifications_list, many=True)
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return Response({
        'notifications': serializer.data,
        'unread_count': unread_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({'message': 'Notification marked as read'})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'message': 'All notifications marked as read'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notifications_count(request):
    """Get unread notifications count"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return Response({'unread_count': count})


# Helper function to create notifications
def create_notification(user, notification_type, title, message, related_session=None, play_sound=True):
    """Helper function to create notifications with sound support"""
    # Get unread count for badge
    unread_count = Notification.objects.filter(user=user, is_read=False).count()
    
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        related_session=related_session,
        sound_played=False if play_sound else True,
        badge_count=unread_count + 1
    )
    
    return notification


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scrape_website_api(request):
    """Scrape website content for AI learning"""
    url = request.data.get('url', '').strip()
    
    if not url:
        return Response({'error': 'URL is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    result = scrape_website_content(url)
    
    if result['success']:
        return Response({
            'message': result['message'],
            'url': result['content'].url,
            'title': result['content'].title,
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': result['message']
        }, status=status.HTTP_400_BAD_REQUEST)

