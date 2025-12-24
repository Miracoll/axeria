from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from account.models import User
from account.utils import get_client_ip, send_verification_email

# Create your views here.

def home(request):
    return render(request, 'interface/index.html')
    
def contact(request):
    return render(request, 'interface/contact.html')

def about(request):
    return render(request, 'interface/about.html')

def education(request):
    return render(request, 'interface/education.html')

def roadmap(request):
    return render(request, 'interface/roadmap.html')

def privacy_policy(request):
    return render(request, 'interface/privacy_policy.html')

def signin_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user_qs = User.objects.filter(username=username).first()
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            user.psw = password
            user.last_login = timezone.now()

            # Get user IP
            ip = get_client_ip(request)
            user.last_login_ip = ip

            user.save()

            if user.groups.filter(name='admin').exists():
                return redirect('admin-home')
            else:
                return redirect('home')

        else:
            if user_qs and not user_qs.is_active:
                messages.error(request, 'Your account is not active.')
            else:
                messages.error(request, 'Incorrect email or password.')

            return redirect('login')

    return render(request, 'interface/signin.html')

def signup_user(request):
    if request.method == 'POST':
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        username = request.POST.get('uname')
        password = request.POST.get('password')
        confirm_password = request.POST.get('cpassword')
        email = request.POST.get('email')

        # Check empty fields
        if not all([first_name, last_name, username, password, confirm_password, email]):
            messages.error(request, 'All fields are required.')
            return redirect('register')

        # Check password match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register')

        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')

        # Create user
        user = User.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            password=password,
            email=email
        )

        user.is_active = False
        user.save()

        # Add default group
        group, _ = Group.objects.get_or_create(name='trader')
        user.groups.add(group)

        # Generate UID and token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Build verification link
        verification_url = request.build_absolute_uri(
            reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
        )

        # Email content
        send_verification_email(user, verification_url)

        messages.success(request, 'Verification sent!')
        return redirect('verification-sent')

    return render(request, 'interface/signup.html')

def verification_sent(request):
    return render(request, 'interface/verification_sent.html')

def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Email verified successfully!")
        return redirect("login")
    else:
        messages.error(request, "Invalid or expired verification link.")
        return redirect("verification-sent")
    
def resend_verification_email(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to resend verification link.")
        return redirect("login")

    user = request.user

    if user.is_active:
        messages.info(request, "Your email is already verified.")
        return redirect("home")  # Change to your preferred page

    # Generate new UID and token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    verification_url = request.build_absolute_uri(
        reverse("verify_email", kwargs={'uidb64': uid, 'token': token})
    )

    # Email content
    send_verification_email(user, verification_url)

    messages.success(request, "A new verification link has been sent to your email.")
    return redirect("verification-sent")

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')