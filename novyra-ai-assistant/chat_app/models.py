"""Consolidated models for Chat App"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ChatSession(models.Model):
    """Represents a chat session between user and system/agent"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('waiting_agent', 'Waiting for Agent'),
        ('agent_assigned', 'Agent Assigned'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    # Customer information
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=30, null=True, blank=True, help_text="International phone number with country code")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    assigned_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    feedback = models.TextField(null=True, blank=True)
    # Track if user has already left a message when waiting
    has_left_message = models.BooleanField(default=False, help_text="Whether user has already left a message while waiting for agent")
    # Track conversation context
    last_intent = models.CharField(max_length=100, null=True, blank=True, help_text="Last detected intent for context")
    ticket_suggested = models.BooleanField(default=False, help_text="Whether ticket creation has been suggested")
    package_selected = models.CharField(max_length=50, null=True, blank=True, help_text="Selected pricing package")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['session_id', 'status'])]
    
    def __str__(self):
        return f"Session {self.session_id} - {self.status}"


class Message(models.Model):
    """Individual messages in a chat session"""
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI Bot'),
        ('agent', 'Human Agent'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    intent_detected = models.CharField(max_length=100, null=True, blank=True)
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    attachment_type = models.CharField(max_length=20, null=True, blank=True, help_text="image, document, audio, video")
    created_at = models.DateTimeField(auto_now_add=True)
    # Read status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='read_messages')
    
    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['session', 'created_at']), models.Index(fields=['is_read', 'created_at'])]
    
    def __str__(self):
        return f"{self.message_type} - {self.session.session_id}"


class KnowledgeBase(models.Model):
    """Knowledge base entries for AI responses"""
    CATEGORY_CHOICES = [
        ('faq', 'FAQ'),
        ('service', 'Service'),
        ('campaign', 'Campaign Help'),
        ('general', 'General'),
        ('escalation', 'Escalation Trigger'),
    ]
    
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    keywords = models.TextField(help_text="Comma-separated keywords for matching")
    content = models.TextField(help_text="Response content")
    intent = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher priority matches first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'title']
        indexes = [models.Index(fields=['category', 'is_active'])]
    
    def __str__(self):
        return f"{self.title} ({self.category})"


class Agent(models.Model):
    """Extended agent information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_profile')
    is_available = models.BooleanField(default=True)
    max_concurrent_chats = models.IntegerField(default=5)
    current_chats = models.IntegerField(default=0)
    total_chats_handled = models.IntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Agent: {self.user.username}"


class AgentChat(models.Model):
    """Agent-to-agent internal chat conversations"""
    participants = models.ManyToManyField(User, related_name='agent_chats')
    title = models.CharField(max_length=200, null=True, blank=True)
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_discussions', help_text='Related customer session if this chat is about a customer')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        participant_names = ', '.join([p.username for p in self.participants.all()[:2]])
        return f"Agent Chat: {participant_names}"


class AgentMessage(models.Model):
    """Messages in agent-to-agent chats"""
    chat = models.ForeignKey(AgentChat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_messages')
    content = models.TextField()
    attachment = models.FileField(upload_to='agent_chat_attachments/', null=True, blank=True)
    attachment_type = models.CharField(max_length=20, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"


class AgentNote(models.Model):
    """Internal notes agents can add to customer sessions"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='agent_notes')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    is_private = models.BooleanField(default=False, help_text='Private notes visible only to the agent who created them')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note by {self.agent.username} on {self.session.session_id}"


class Analytics(models.Model):
    """System analytics and metrics"""
    date = models.DateField(default=timezone.now)
    total_sessions = models.IntegerField(default=0)
    ai_resolved = models.IntegerField(default=0)
    agent_resolved = models.IntegerField(default=0)
    average_response_time = models.FloatField(default=0.0)
    average_rating = models.FloatField(default=0.0)
    escalation_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Analytics - {self.date}"


class UserProfile(models.Model):
    """Extended user profile with profile picture and settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile: {self.user.username}"


class LoginHistory(models.Model):
    """Track user login history"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device = models.CharField(max_length=100, null=True, blank=True)
    browser = models.CharField(max_length=100, null=True, blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    
    class Meta:
        ordering = ['-login_time']
        verbose_name_plural = 'Login Histories'
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


class Notification(models.Model):
    """System notifications for users"""
    NOTIFICATION_TYPES = [
        ('message', 'New Message'),
        ('session', 'New Session'),
        ('escalation', 'Escalation'),
        ('ticket', 'New Ticket'),
        ('system', 'System'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sound_played = models.BooleanField(default=False, help_text="Whether notification sound has been played")
    badge_count = models.IntegerField(default=0, help_text="Badge count for notification tabs")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read', 'created_at'])]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Ticket(models.Model):
    """Support tickets for unresolved issues"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='tickets')
    ticket_number = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Follow-up tracking
    follow_up_notes = models.TextField(null=True, blank=True, help_text="Internal notes for follow-up actions")
    follow_up_date = models.DateTimeField(null=True, blank=True, help_text="Scheduled follow-up date")
    follow_up_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_to_follow_up')
    customer_notified = models.BooleanField(default=False, help_text="Whether customer has been notified via email")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'priority', 'created_at']), models.Index(fields=['follow_up_date', 'status'])]
    
    def __str__(self):
        return f"Ticket {self.ticket_number} - {self.title}"


class ConversationLearning(models.Model):
    """Store conversation patterns for ML learning"""
    user_message = models.TextField()
    ai_response = models.TextField()
    intent_detected = models.CharField(max_length=100, null=True, blank=True)
    confidence = models.FloatField(default=0.0)
    was_helpful = models.BooleanField(null=True, blank=True)  # User feedback
    escalated = models.BooleanField(default=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='learning_data')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['intent_detected', 'was_helpful', 'created_at'])]
    
    def __str__(self):
        return f"Learning: {self.intent_detected} - {self.created_at}"


class BusinessHours(models.Model):
    """Business hours configuration"""
    day_of_week = models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), 
                                                (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])
    is_open = models.BooleanField(default=True)
    open_time = models.TimeField(default='08:00')
    close_time = models.TimeField(default='20:00')
    timezone = models.CharField(max_length=50, default='GMT+1')
    
    class Meta:
        ordering = ['day_of_week']
        unique_together = ['day_of_week']
    
    def __str__(self):
        return f"{self.get_day_of_week_display()} - {self.open_time} to {self.close_time}"


class ChatWidgetConfig(models.Model):
    """Configuration for embeddable chat widget"""
    name = models.CharField(max_length=100, default='Default Widget')
    bot_name = models.CharField(max_length=100, default='Ariho', help_text='Name of the AI bot assistant')
    bot_profile_image = models.ImageField(upload_to='bot_profiles/', null=True, blank=True, help_text='Profile image for the bot')
    button_color = models.CharField(max_length=7, default='#0006B1', help_text='Hex color for the chat button')
    button_position = models.CharField(max_length=20, choices=[
        ('bottom-right', 'Bottom Right'),
        ('bottom-left', 'Bottom Left'),
        ('top-right', 'Top Right'),
        ('top-left', 'Top Left'),
    ], default='bottom-right')
    widget_width = models.IntegerField(default=420, help_text='Width in pixels')
    widget_height = models.IntegerField(default=600, help_text='Height in pixels')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.button_color}"


class WebsiteContent(models.Model):
    """Store website content for AI learning"""
    url = models.URLField(unique=True, db_index=True)
    title = models.CharField(max_length=500, null=True, blank=True)
    content = models.TextField(help_text="Extracted text content from the webpage")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata like headings, links, etc.")
    last_scraped = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-last_scraped']
        indexes = [models.Index(fields=['url', 'is_active'])]
    
    def __str__(self):
        return f"{self.title or self.url} - {self.last_scraped}"

