from django.urls import path

from . import views
from . import telegram_profile as profile_views

app_name = 'supporthub'

urlpatterns = [
    path('telegram/me/', profile_views.telegram_profile, name='telegram_profile'),
    path('telegram/me/link/', profile_views.start_pairing, name='telegram_link'),
    path('telegram/me/confirm/', profile_views.confirm_pairing, name='telegram_confirm'),
    path('telegram/me/preferences/', profile_views.save_preferences, name='telegram_preferences'),
    path('telegram/me/disable/', profile_views.unlink_chat, name='telegram_disable'),
    path('', views.inbox, name='inbox'),
    path('settings/', views.settings_page, name='settings'),
    path('telegram/bot/', views.bot_form, name='bot_edit'),
    path('telegram/bot/test/', views.bot_test, name='bot_test'),
    path('telegram/chats/discover/', views.discover_telegram_chats, name='telegram_chats_discover'),
    path('portals/new/', views.portal_form, name='portal_new'),
    path('portals/<int:pk>/edit/', views.portal_form, name='portal_edit'),
    path('chats/new/', views.chat_form, name='chat_new'),
    path('chats/<int:pk>/edit/', views.chat_form, name='chat_edit'),
    path('recipients/new/', views.recipient_form, name='recipient_new'),
    path('recipients/<int:pk>/edit/', views.recipient_form, name='recipient_edit'),
    path('recipients/<int:pk>/test/', views.test_recipient, name='recipient_test'),
    path('shifts/new/', views.shift_form, name='shift_new'),
    path('shifts/<int:pk>/edit/', views.shift_form, name='shift_edit'),
    path('delete/<str:kind>/<int:pk>/', views.delete_item, name='delete_item'),
    path('notices/<int:pk>/retry/', views.retry_notice, name='notice_retry'),
]
