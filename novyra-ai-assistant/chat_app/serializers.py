"""DRF Serializers for Chat App"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import ChatSession, Message, KnowledgeBase, Agent, Analytics, UserProfile, LoginHistory, Notification, AgentChat, AgentMessage, AgentNote


class MessageSerializer(serializers.ModelSerializer):
    attachment_url = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()
    sender_profile_picture = serializers.SerializerMethodField()
    read_by_profile_picture = serializers.SerializerMethodField()
    read_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'message_type', 'content', 'sender', 'sender_name', 'sender_profile_picture', 
                  'ai_confidence', 'intent_detected', 'attachment', 'attachment_type', 'attachment_url', 
                  'is_read', 'read_at', 'read_by', 'read_by_name', 'read_by_profile_picture', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_read', 'read_at', 'read_by']
    
    def get_attachment_url(self, obj):
        if obj.attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None
    
    def get_sender_name(self, obj):
        """Get sender name for agent messages"""
        if obj.sender and hasattr(obj.sender, 'username'):
            # If it's a user (agent), return their full name or username
            if hasattr(obj.sender, 'first_name') and obj.sender.first_name:
                full_name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
                return full_name if full_name else obj.sender.username
            return obj.sender.username
        return None
    
    def get_sender_profile_picture(self, obj):
        """Get sender profile picture URL"""
        if obj.sender:
            try:
                profile = obj.sender.user_profile
                if profile.profile_picture:
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(profile.profile_picture.url)
                    return profile.profile_picture.url
            except UserProfile.DoesNotExist:
                pass
        return None
    
    def get_read_by_profile_picture(self, obj):
        """Get read_by profile picture URL for seen indicator"""
        if obj.read_by:
            try:
                profile = obj.read_by.user_profile
                if profile.profile_picture:
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(profile.profile_picture.url)
                    return profile.profile_picture.url
            except UserProfile.DoesNotExist:
                pass
        return None
    
    def get_read_by_name(self, obj):
        """Get read_by name"""
        if obj.read_by:
            if hasattr(obj.read_by, 'first_name') and obj.read_by.first_name:
                full_name = f"{obj.read_by.first_name} {obj.read_by.last_name}".strip()
                return full_name if full_name else obj.read_by.username
            return obj.read_by.username
        return None


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    assigned_agent_username = serializers.CharField(source='assigned_agent.username', read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'session_id', 'status', 'assigned_agent', 'assigned_agent_username', 
                  'customer_name', 'customer_email', 'customer_phone',
                  'created_at', 'updated_at', 'rating', 'feedback', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatSessionListSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'session_id', 'status', 'assigned_agent', 'customer_name', 'customer_email', 'customer_phone', 'created_at', 'last_message', 'message_count']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        return MessageSerializer(last_msg, context=self.context).data if last_msg else None


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = ['id', 'title', 'category', 'keywords', 'content', 'intent', 'is_active', 'priority']
        read_only_fields = ['id']


class ChatRequestSerializer(serializers.Serializer):
    """Serializer for incoming chat messages"""
    session_id = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=True)
    user_ip = serializers.CharField(required=False, allow_blank=True)
    user_agent = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat responses"""
    session_id = serializers.CharField()
    message = serializers.CharField()
    message_type = serializers.CharField()
    ai_confidence = serializers.FloatField(required=False)
    intent_detected = serializers.CharField(required=False)
    status = serializers.CharField()
    escalation_triggered = serializers.BooleanField(default=False)


class AgentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Agent
        fields = ['id', 'user', 'username', 'email', 'first_name', 'last_name', 'profile_picture_url',
                  'is_available', 'max_concurrent_chats', 'current_chats', 'total_chats_handled', 'average_rating']
        read_only_fields = ['id', 'total_chats_handled', 'average_rating']
    
    def get_profile_picture_url(self, obj):
        """Get agent profile picture URL"""
        try:
            profile = obj.user.user_profile
            if profile.profile_picture:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(profile.profile_picture.url)
                return profile.profile_picture.url
        except UserProfile.DoesNotExist:
            pass
        return None


class AnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analytics
        fields = ['date', 'total_sessions', 'ai_resolved', 'agent_resolved', 
                  'average_response_time', 'average_rating', 'escalation_count']


class UserProfileSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'username', 'email', 'first_name', 'last_name', 
                  'profile_picture', 'profile_picture_url', 'phone_number', 'bio', 
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ['id', 'ip_address', 'user_agent', 'device', 'browser', 
                  'login_time', 'logout_time']
        read_only_fields = ['id', 'login_time', 'logout_time']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message', 'is_read', 
                  'related_session', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)


class AgentMessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AgentMessage
        fields = ['id', 'sender', 'content', 'attachment_url', 'attachment_type', 
                  'is_read', 'read_at', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_sender(self, obj):
        if obj.sender:
            return {
                'id': obj.sender.id,
                'username': obj.sender.username,
                'name': f"{obj.sender.first_name} {obj.sender.last_name}".strip() or obj.sender.username
            }
        return None
    
    def get_attachment_url(self, obj):
        if obj.attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None


class AgentChatSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AgentChat
        fields = ['id', 'title', 'participants', 'session', 'is_active', 
                  'last_message', 'unread_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_participants(self, obj):
        return [{
            'id': p.id,
            'username': p.username,
            'name': f"{p.first_name} {p.last_name}".strip() or p.username,
            'email': p.email
        } for p in obj.participants.all()]
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return AgentMessageSerializer(last_msg, context=self.context).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0


class AgentNoteSerializer(serializers.ModelSerializer):
    agent_username = serializers.CharField(source='agent.username', read_only=True)
    agent_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AgentNote
        fields = ['id', 'session', 'agent', 'agent_username', 'agent_name', 
                  'note', 'is_private', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_agent_name(self, obj):
        if obj.agent:
            full_name = f"{obj.agent.first_name} {obj.agent.last_name}".strip()
            return full_name if full_name else obj.agent.username
        return None

