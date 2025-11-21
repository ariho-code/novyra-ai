"""URL routing for Chat App"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    ChatSessionViewSet, KnowledgeBaseViewSet, AgentViewSet,
    chat_api, get_session_messages, analytics_api, upload_file,
    user_profile, upload_profile_picture, change_password, login_history,
    notifications, mark_notification_read, mark_all_notifications_read,
    unread_notifications_count, faqs_api, services_api, services_detail_api, pricing_api, agent_availability_api,
    common_questions_api, create_ticket_api, embed_widget, embed_code, widget_config_api, update_widget_config_api,
    agent_chats_api, agent_chat_messages_api, agent_chat_add_participant_api, agent_notes_api, delete_message_api,
    mark_message_read_api, ticket_follow_up_api, scrape_website_api
)

router = DefaultRouter()
router.register(r'sessions', ChatSessionViewSet, basename='session')
router.register(r'knowledge-base', KnowledgeBaseViewSet, basename='knowledgebase')
router.register(r'agents', AgentViewSet, basename='agent')

urlpatterns = [
    # Authentication
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Chat API (public)
    path('chat/', chat_api, name='chat'),
    path('chat/<str:session_id>/messages/', get_session_messages, name='session-messages'),
    path('chat/upload/', upload_file, name='upload-file'),
    path('messages/<int:message_id>/', delete_message_api, name='delete-message'),
    path('messages/<int:message_id>/read/', mark_message_read_api, name='mark-message-read'),
    
    # FAQs and Services
    path('faqs/', faqs_api, name='faqs'),
    path('services/', services_api, name='services'),
    path('services/detailed/', services_detail_api, name='services-detailed'),
    path('pricing/', pricing_api, name='pricing'),
    path('common-questions/', common_questions_api, name='common-questions'),
    
    # Agent Availability
    path('agent-availability/', agent_availability_api, name='agent-availability'),
    
    # Tickets
    path('tickets/create/', create_ticket_api, name='create-ticket'),
    path('tickets/<int:ticket_id>/follow-up/', ticket_follow_up_api, name='ticket-follow-up'),
    
    # Embed Widget
    path('widget-config/', widget_config_api, name='widget-config'),
    path('widget-config/update/', update_widget_config_api, name='widget-config-update'),
    path('embed/', embed_widget, name='embed-widget'),
    path('embed/<int:config_id>/', embed_widget, name='embed-widget-config'),
    path('embed-code/', embed_code, name='embed-code'),
    path('embed-code/<int:config_id>/', embed_code, name='embed-code-config'),
    
    # Agent Chat
    path('agent-chats/', agent_chats_api, name='agent-chats'),
    path('agent-chats/<int:chat_id>/messages/', agent_chat_messages_api, name='agent-chat-messages'),
    path('agent-chats/<int:chat_id>/add-participant/', agent_chat_add_participant_api, name='agent-chat-add-participant'),
    
    # Agent Notes
    path('sessions/<str:session_id>/notes/', agent_notes_api, name='agent-notes'),
    
    # Analytics
    path('analytics/', analytics_api, name='analytics'),
    
    # Profile Management
    path('profile/', user_profile, name='user-profile'),
    path('profile/picture/', upload_profile_picture, name='upload-profile-picture'),
    path('profile/change-password/', change_password, name='change-password'),
    path('profile/login-history/', login_history, name='login-history'),
    
    # Notifications
    path('notifications/', notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', mark_notification_read, name='mark-notification-read'),
    path('notifications/read-all/', mark_all_notifications_read, name='mark-all-read'),
    path('notifications/unread-count/', unread_notifications_count, name='unread-count'),
    
    # Website Content Scraping
    path('website-content/scrape/', scrape_website_api, name='scrape-website'),
    
    # Router URLs
    path('', include(router.urls)),
]

