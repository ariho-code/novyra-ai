"""novyra_ai URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from chat_app.views import api_root, chat_interface, admin_dashboard, login_view, logout_view

admin.site.site_header = "Novyra AI Assistant Admin"
admin.site.site_title = "Novyra AI Admin"
admin.site.index_title = "Welcome to Novyra AI Assistant Administration"

urlpatterns = [
    path('', chat_interface, name='chat-interface'),
    path('api-root/', api_root, name='api-root'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', admin_dashboard, name='admin-dashboard'),
    path('admin/', admin.site.urls),
    path('api/', include('chat_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

