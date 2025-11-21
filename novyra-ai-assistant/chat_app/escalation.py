"""Escalation Module - Handles chat escalation to human agents"""
from typing import Optional
from django.contrib.auth.models import User
from django.db.models import F
from .models import ChatSession, Agent, Message


class EscalationHandler:
    """Handles escalation logic and agent assignment"""
    
    @staticmethod
    def find_available_agent() -> Optional[User]:
        """Find an available agent with capacity"""
        try:
            # First, ensure Agent profiles exist for staff users
            from django.contrib.auth.models import User
            staff_users = User.objects.filter(is_staff=True, is_active=True)
            print(f"🔍 Found {staff_users.count()} staff users")
            
            for user in staff_users:
                if not hasattr(user, 'agent_profile'):
                    Agent.objects.get_or_create(
                        user=user,
                        defaults={
                            'is_available': True,
                            'max_concurrent_chats': 5,
                            'current_chats': 0
                        }
                    )
                    print(f"✅ Created agent profile for {user.username}")
            
            # Find available agent with capacity
            agent_profile = Agent.objects.filter(
                is_available=True,
                user__is_active=True,
                current_chats__lt=F('max_concurrent_chats')
            ).order_by('current_chats').first()
            
            if agent_profile:
                print(f"✅ Found available agent: {agent_profile.user.username} (current_chats={agent_profile.current_chats}, max={agent_profile.max_concurrent_chats})")
                return agent_profile.user
            else:
                print(f"⚠️ No available agent found with capacity")
                # Fallback: find any available agent
                agent_profile = Agent.objects.filter(is_available=True, user__is_active=True).first()
                if agent_profile:
                    print(f"⚠️ Found agent but at capacity: {agent_profile.user.username} (current_chats={agent_profile.current_chats}, max={agent_profile.max_concurrent_chats})")
                return agent_profile.user if agent_profile else None
        except Exception as e:
            print(f"❌ Error finding available agent: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: find any available agent
            try:
                agent_profile = Agent.objects.filter(is_available=True, user__is_active=True).first()
                return agent_profile.user if agent_profile else None
            except Exception:
                return None
    
    @staticmethod
    def assign_agent(session: ChatSession) -> bool:
        """Assign an available agent to a session"""
        # Don't reassign if agent is already assigned
        if session.assigned_agent:
            return True
        
        agent = EscalationHandler.find_available_agent()
        
        if agent:
            try:
                print(f"🔍 Assigning agent {agent.username} to session {session.session_id[:8]}")
                session.assigned_agent = agent
                session.status = 'agent_assigned'
                session.save()
                print(f"✅ Session saved with agent assignment")
                
                # Update agent's current chat count
                try:
                    # Check if agent_profile exists
                    if hasattr(agent, 'agent_profile'):
                        try:
                            agent_profile = agent.agent_profile
                            # Use atomic update to avoid race conditions
                            Agent.objects.filter(id=agent_profile.id).update(current_chats=F('current_chats') + 1)
                            print(f"✅ Updated agent chat count for {agent.username}")
                        except Exception as profile_error:
                            print(f"⚠️ Error accessing agent profile: {profile_error}")
                            # Create agent profile if it doesn't exist
                            Agent.objects.get_or_create(
                                user=agent,
                                defaults={
                                    'is_available': True,
                                    'max_concurrent_chats': 5,
                                    'current_chats': 1
                                }
                            )
                    else:
                        # Create agent profile if it doesn't exist
                        Agent.objects.get_or_create(
                            user=agent,
                            defaults={
                                'is_available': True,
                                'max_concurrent_chats': 5,
                                'current_chats': 1
                            }
                        )
                        print(f"✅ Created agent profile for {agent.username}")
                except Exception as profile_error:
                    print(f"⚠️ Error updating agent profile: {profile_error}")
                    # Still continue - agent is assigned even if profile update fails
                
                # Verify assignment was successful
                session.refresh_from_db()
                if session.assigned_agent and session.assigned_agent.id == agent.id:
                    print(f"✅ VERIFIED: Agent {agent.username} successfully assigned to session {session.session_id[:8]}")
                    return True
                else:
                    print(f"❌ VERIFICATION FAILED: Agent assignment did not persist. Expected: {agent.id}, Got: {session.assigned_agent.id if session.assigned_agent else None}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error assigning agent: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # No agent available - set status to waiting
        print(f"⚠️ No available agent found for session {session.session_id[:8]}")
        session.status = 'waiting_agent'
        session.save()
        
        Message.objects.create(
            session=session,
            message_type='system',
            content='All our agents are currently busy. Your chat will be assigned to an agent shortly. Thank you for your patience.',
        )
        return False
    
    @staticmethod
    def release_agent(session: ChatSession):
        """Release agent when session is closed"""
        if session.assigned_agent:
            try:
                agent_profile = session.assigned_agent.agent_profile
                agent_profile.current_chats = max(0, agent_profile.current_chats - 1)
                agent_profile.total_chats_handled += 1
                agent_profile.save()
            except Agent.DoesNotExist:
                pass

