"""
URL configuration for axeria project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('super/', admin.site.urls),
    path('', include('interface.urls')),
    path('account/', include('account.urls')),
    path('control/', include('manager.urls')),

    path(
        'forgot-password/',
        auth_views.PasswordResetView.as_view(
            template_name='interface/forgot_password.html',
            email_template_name='email_templates/reset_password_email.txt',
            html_email_template_name='email_templates/reset_password_email.html',
            subject_template_name='email_templates/reset_subject.txt',
            success_url=reverse_lazy('password_reset_done')
        ),
        name='password_reset'
    ),

    path(
        'forgot-password/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='interface/forgot_password_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='interface/reset_password_confirm.html',
            success_url=reverse_lazy('password_reset_complete')
        ),
        name='password_reset_confirm'
    ),

    path(
        'reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='interface/reset_password_complete.html'
        ),
        name='password_reset_complete'
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)