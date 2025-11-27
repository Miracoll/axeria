from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.home, name='admin-home'),
    path('withdrawal/', views.withdrawal, name='admin-withdrawal'),
    path('create-trader/', views.create_trader, name='admin-create-trader'),
    path('experts/', views.expert, name='admin-experts'),
    path('edit-users/', views.edit_users, name='admin-edit-user'),
    path('manage-trades/', views.manage_trade, name='admin-manage-trade'),
    path('activate/', views.activate, name='admin-activate'),
    path('kyc', views.kyc, name='admin-kyc'),
    path('edit-portfolio/', views.edit_portfolio, name='admin-edit-portfolio'),
    path('active-trade/', views.active_trade, name='admin-active-trade'),
    path('promotional-email/', views.newsletter, name='admin-newsletter'),
    path('messages/', views.message, name='admin-message'),
    path('change-password/', views.change_password, name='admin-change-password'),
    path('change-email/', views.change_email, name='admin-change-email'),
    path('change-username/', views.change_username, name='admin-change-username'),
    path('site-info/', views.site_info, name='admin-site-info'),
    path('plans/', views.plans, name='admin-plans'),
    path('payments/', views.payments, name='admin-payments'),
    path('withdraw/approve/<int:id>/', views.approve_withdrawal, name='approve_withdrawal'),
    path('withdraw/decline/<int:id>/', views.decline_withdrawal, name='decline_withdrawal'),
]