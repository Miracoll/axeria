from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.models import Group
from django.utils import timezone

from account.models import User
from account.utils import get_client_ip

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

        # Add default group
        group, _ = Group.objects.get_or_create(name='trader')
        user.groups.add(group)

        # Login user automatically (optional)
        login(request, user)

        messages.success(request, 'Account created successfully!')
        return redirect('home')

    return render(request, 'interface/signup.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')