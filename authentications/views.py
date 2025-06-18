from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_backends
from django.contrib.auth.decorators import login_required
#from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from .models import *
from mainApp.models import Order, CartItem

from .forms import SignupForm, UserProfileForm, OTPForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from .utils import generate_otp, send_otp_via_email
from django.views.decorators.csrf import csrf_protect

# Create your views here.
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=False
            )
            user.save()

            otp = generate_otp()
            request.session['otp'] = otp
            request.session['user_id'] = user.id

            send_otp_via_email(user.email, otp)

            return redirect('verify_otp')  # Redirect to OTP form page
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

def verify_otp_view(request):
    if request.method == 'POST':
        input_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')
        user_id = request.session.get('user_id')

        if input_otp == session_otp and user_id:
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.save()

            # Specify backend manually
            backend = get_backends()[0]
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
            login(request, user)

            # Clean session data
            request.session.pop('otp')
            request.session.pop('user_id')

            messages.success(request, 'OTP verified! You are now logged in.')
            return redirect('home')
        else:
            messages.error(request, 'Invalid OTP, please try again.')

    return render(request, 'verify_otp.html')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('profile')
    else:
        return render(request, 'activation_invalid.html')

@csrf_protect
def custom_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect('profile')
        else:
            messages.error(request, "Invalid email or password.")
            return redirect('home')
    else:
        return redirect('home')


def user_logout(request):
    logout(request)
    return redirect('home')


# Profile View
@login_required
def profile(request):
    user = request.user
    profile = getattr(user, 'userprofile', None)

    purchase_history = Order.objects.filter(user=user).order_by('-ordered_at')
    cart_items = CartItem.objects.filter(user=user)

    context = {
        'profile': profile,
        'cart_items': cart_items,
        'purchase_history': purchase_history,
    }
    return render(request, 'profile.html', context)

# Update Profile View
@login_required
def update_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('profile')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'profile_update.html', {'profile_form': profile_form})

# Change Password View
@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'change_password.html', {'form': form})

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('profile')
