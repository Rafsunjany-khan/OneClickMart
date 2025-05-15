from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import UserProfile, Slider, Product

def home(request):
    sliders = Slider.objects.all()
    products = Product.objects.filter(available=True).prefetch_related('images')
    return render(request, 'base.html', {'sliders': sliders, 'products': products})

def signup(request):
    if request.method == 'POST':
        fname = request.POST['first_name']
        lname = request.POST['last_name']
        email = request.POST['email']
        password = request.POST['password']
        confirm = request.POST['confirm_password']

        if password == confirm:
            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = fname
            user.last_name = lname
            user.save()
            return redirect('login')  # or wherever
    return render(request, 'signup.html')


def custom_login(request):
    if request.method == 'POST':
        print(request.POST)  # Log the entire POST data
        email = request.POST.get('email')  # or 'email' depending on the form field name
        password = request.POST.get('password')

        print(f"Attempting to authenticate user: {email}, password: {password}")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            print(f"Authentication successful for: {user.username}")
            login(request, user)
            return redirect('profile')
        else:
            print("Authentication failed.")
            messages.error(request, "Invalid email or password.")
            return redirect('home')  # Keep the user on the same page
    return redirect('home')




@login_required
def profile(request):
    user = request.user  # ✅ This is always the currently logged-in user
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        profile.profile_image = request.FILES.get('profile_image')
        profile.address_line_1 = request.POST.get('address_line_1')
        profile.address_line_2 = request.POST.get('address_line_2')
        profile.phone_number = request.POST.get('phone_number')
        profile.city = request.POST.get('city')
        profile.postcode = request.POST.get('postcode')
        profile.save()
        return redirect('profile')

    return render(request, 'profile.html', {'profile': profile})


# Remove the redundant profile function that checks the session

def user_logout(request):
    logout(request)
    return redirect('home')


def cart_view(request):
    cart = request.session.get('cart', {})
    total = 0

    for key, item in cart.items():
        item['total_price'] = item['price'] * item['quantity']  # add total per item
        total += item['total_price']

    return render(request, 'cart.html', {
        'cart': cart,
        'total': total
    })


def update_cart(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        action = request.POST.get('action')

        if action:
            action_type, product_id = action.split('_', 1)
            if product_id in cart:
                if action_type == 'add':
                    cart[product_id]['quantity'] += 1
                elif action_type == 'remove':
                    cart[product_id]['quantity'] -= 1
                    if cart[product_id]['quantity'] <= 0:
                        del cart[product_id]

        request.session['cart'] = cart
    return redirect('cart')


#@csrf_exempt
def clear_cart(request):
    if request.method == 'POST':
        request.session.pop('cart', None)
    return redirect('cart')
