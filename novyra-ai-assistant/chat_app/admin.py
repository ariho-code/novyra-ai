"""Admin configuration for Chat App"""
from django.contrib import admin
from .models import ChatSession, Message, KnowledgeBase, Agent, Analytics, UserProfile, LoginHistory, Notification, Ticket, ConversationLearning, BusinessHours, ChatWidgetConfig, WebsiteContent


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'status', 'assigned_agent', 'created_at', 'rating']
    list_filter = ['status', 'created_at']
    search_fields = ['session_id', 'user_ip']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'message_type', 'content_preview', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['content', 'session__session_id']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'intent', 'is_active', 'priority']
    list_filter = ['category', 'is_active']
    search_fields = ['title', 'keywords', 'content']
    list_editable = ['is_active', 'priority']


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_available', 'current_chats', 'total_chats_handled', 'average_rating']
    list_filter = ['is_available']
    search_fields = ['user__username']


@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sessions', 'ai_resolved', 'agent_resolved', 'average_rating']
    list_filter = ['date']
    readonly_fields = ['date']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'device', 'browser', 'login_time', 'logout_time']
    list_filter = ['login_time', 'device', 'browser']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['login_time']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'title', 'status', 'priority', 'assigned_agent', 'created_at']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['ticket_number', 'title', 'description']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']


@admin.register(ConversationLearning)
class ConversationLearningAdmin(admin.ModelAdmin):
    list_display = ['session', 'intent_detected', 'confidence', 'was_helpful', 'escalated', 'created_at']
    list_filter = ['intent_detected', 'was_helpful', 'escalated', 'created_at']
    search_fields = ['user_message', 'ai_response', 'session__session_id']
    readonly_fields = ['created_at']


@admin.register(BusinessHours)
class BusinessHoursAdmin(admin.ModelAdmin):
    list_display = ['day_of_week', 'is_open', 'open_time', 'close_time', 'timezone']
    list_filter = ['is_open', 'day_of_week']
    list_editable = ['is_open', 'open_time', 'close_time']


@admin.register(ChatWidgetConfig)
class ChatWidgetConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'button_color', 'button_position', 'widget_width', 'widget_height', 'is_active', 'created_at']
    list_filter = ['is_active', 'button_position', 'created_at']
    list_editable = ['is_active', 'button_color', 'button_position']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WebsiteContent)
class WebsiteContentAdmin(admin.ModelAdmin):
    list_display = ['title', 'url', 'is_active', 'last_scraped', 'created_at']
    list_filter = ['is_active', 'last_scraped', 'created_at']
    search_fields = ['url', 'title', 'content']
    list_editable = ['is_active']
    readonly_fields = ['last_scraped', 'created_at']

