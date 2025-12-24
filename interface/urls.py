from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.home, name='interface-home'),
    path('contact/', views.contact, name='interface-contact'),
    path('about/', views.about, name='interface-about'),
    path('education/', views.education, name='interface-education'),
    path('roadmap/', views.roadmap, name='interface-roadmap'),
    path('privacy-policy/', views.privacy_policy, name='interface-privacy-policy'),
    path('login/', views.signin_user, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.signup_user, name='register'),
    path('verification/', views.verification_sent, name='verification-sent'),
    path('verify/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name="resend-verification"),
]