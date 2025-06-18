import requests,uuid
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import *
from django.urls import reverse

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


# Home Page
def home(request):
    sliders = Slider.objects.all()
    products = Product.objects.filter(available=True).order_by('-created_at').prefetch_related('images')
    return render(request, 'base.html', {'sliders': sliders, 'products': products})

def product_list(request):
    products = Product.objects.filter(available=True).order_by('-created_at').prefetch_related('images')
    return render(request, 'products.html', {'products': products})

# Product Detail Page
def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    return render(request, 'product_detail.html', {'product': product})

# Add to Cart
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        order__isnull=True,
        is_paid=False,
        defaults={'quantity': 1, 'price_at_added_time': product.get_discounted_price()}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.price_at_added_time = product.get_discounted_price()  # update price if needed
        cart_item.save()

    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart')

#View Cart Page
@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user, order__isnull=True, is_paid=False).select_related('product')
    print(f"DEBUG: Cart items count = {cart_items.count()}")
    for item in cart_items:
        print(f"DEBUG: {item.product.name}, quantity: {item.quantity}, order: {item.order}, paid: {item.is_paid}")
    total = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total,
    })

#Add or Remove Cart Items
@login_required
def update_cart(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')

        if not product_id or not action:
            print("❌ Missing product_id or action in POST data.")
            return redirect('cart')

        product = get_object_or_404(Product, id=product_id)

        cart_item_qs = CartItem.objects.filter(user=request.user, product=product, order__isnull=True, is_paid=False)

        if cart_item_qs.exists():
            cart_item = cart_item_qs.first()
            if action == 'add':
                cart_item.quantity += 1
                cart_item.save()
                print(f"✅ Added 1 to quantity for {product.name}. New quantity: {cart_item.quantity}")
            elif action == 'remove':
                if cart_item.quantity > 1:
                    cart_item.quantity -= 1
                    cart_item.save()
                    print(f"✅ Removed 1 from quantity for {product.name}. New quantity: {cart_item.quantity}")
                else:
                    cart_item.delete()
                    print(f"🗑️ Deleted cart item for {product.name}.")
        else:
            if action == 'add':
                CartItem.objects.create(user=request.user, product=product, quantity=1, is_paid=False)
                print(f"🆕 Created new cart item for {product.name} with quantity 1.")
            else:
                print(f"❌ No cart item to remove for {product.name}.")

        # Debug print all cart items after update
        print(f"Cart items for user {request.user} after update:")
        for ci in CartItem.objects.filter(user=request.user, order__isnull=True, is_paid=False):
            print(f" - Product: {ci.product.name}, Quantity: {ci.quantity}, Paid: {ci.is_paid}, Order: {ci.order}")

    else:
        print("❌ update_cart called with non-POST method.")

    return redirect('cart')

#Clear All Cart Items
@login_required
def clear_cart(request):
    if request.method == 'POST':
        CartItem.objects.filter(user=request.user, order__isnull=True, is_paid=False).delete()
        return redirect('cart')
    return redirect('cart')

@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user, is_paid=False)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('cart')

    if request.method == 'POST':
        total_price = sum(item.product.get_discounted_price() * item.quantity for item in cart_items)

        # Create the order
        order = Order.objects.create(
            user=request.user,
            total_amount=total_price,
            status='Pending',
            shipping_address=request.user.userprofile.address_line_1  # Optional: use profile
        )

        # Create OrderItems for each cart item
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.get_discounted_price(),
            )
            # Link cart items to this order
            item.order = order
            item.is_paid = True  # Mark as processed
            item.save()

        # Store order ID in session for the payment step
        request.session['pending_order_id'] = order.id

        return redirect('make_payment')  # Replace with your actual URL name

    else:
        total_price = sum(item.product.get_discounted_price() * item.quantity for item in cart_items)
        return render(request, 'checkout.html', {
            'cart_items': cart_items,
            'total_price': total_price,
        })

@login_required
def order_success(request):
    return render(request, 'order_success.html')

def update_stock(order):
    for item in order.items.all():
        product = item.product
        # reduce stock only if available
        if product.stock >= item.quantity:
            product.stock -= item.quantity
            product.save()
        else:
            # Handle out of stock scenario if needed
            pass


def some_sslcommerz_api_call(data):
    sslcommerz_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"  # Sandbox URL, use live URL for production

    # Include mandatory store credentials from settings
    payload = {
        'store_id': settings.SSLCOMMERZ_STORE_ID,
        'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
        **data
    }

    try:
        response = requests.post(sslcommerz_url, data=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # You can log the exception here for debugging
        return {'status': 'FAILED', 'error': str(e)}

# Payment Page (Choose Payment Method)

@login_required
def make_payment(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user, is_paid=False, order__isnull=True)

    if not cart_items.exists():
        messages.warning(request, "No items in your cart.")
        return redirect('cart')

    total_amount = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')

        if payment_method == 'cash':
            order = Order.objects.create(
                user=user,
                total_amount=total_amount,
                payment_method='cash',
                status='Completed'
            )
            for item in cart_items:
                item.order = order
                item.is_paid = True
                item.save()
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                item.product.stock_quantity -= item.quantity
                item.product.save()
            messages.success(request, "Order placed successfully with Cash.")
            return redirect('order_confirmation', order_id=order.id)

        elif payment_method == 'sslcommerz':
            order = Order.objects.create(
                user=user,
                total_amount=total_amount,
                payment_method='SSLCommerz',
                status='Pending'
            )
            for item in cart_items:
                item.order = order
                item.is_paid = False
                item.save()
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            return redirect('sslcommerz_payment', order_id=order.id)

    return render(request, 'make_payment.html', {
        'cart_items': cart_items,
        'total_amount': total_amount
    })

@login_required
def process_payment(request):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        user = request.user
        order_id = request.session.get('pending_order_id')

        if not order_id:
            messages.error(request, "No pending order found.")
            return redirect('cart')

        order = get_object_or_404(Order, id=order_id, user=user)

        if payment_method == 'Cash':
            update_stock(order)

            # Clear session and redirect
            request.session.pop('pending_order_id', None)
            messages.success(request, "Your order has been placed successfully with Cash payment.")
            return redirect('order_success')

        elif payment_method == 'SSLCommerz':
            ssl_data = {
                'total_amount': order.total_amount,
                'currency': 'BDT',
                'tran_id': str(uuid.uuid4()),  # unique transaction id
                'success_url': request.build_absolute_uri(reverse('payment_success', kwargs={'order_id': order.id})),
                'fail_url': request.build_absolute_uri(reverse('payment_fail', kwargs={'order_id': order.id})),
                'cancel_url': request.build_absolute_uri(reverse('payment_cancel', kwargs={'order_id': order.id})),
                'cus_name': user.get_full_name(),
                'cus_email': user.email,
                'cus_add1': user.userprofile.address_line_1 if hasattr(user, 'userprofile') else 'N/A',
                'cus_phone': user.userprofile.phone if hasattr(user, 'userprofile') else 'N/A',
                'shipping_method': 'NO',
                'product_name': f"Order#{order.id}",
                'product_category': 'General',
                'product_profile': 'general',
            }

            # Simulate SSLCommerz API call (replace with actual integration)
            response = some_sslcommerz_api_call(ssl_data)

            if response.get('status') == 'SUCCESS' and response.get('GatewayPageURL'):
                return redirect(response['GatewayPageURL'])
            else:
                messages.error(request, f"SSLCommerz Error: {response.get('error', 'Unknown error')}")
                return redirect('cart')
        else:
            messages.error(request, "Invalid payment method selected.")
            return redirect('make_payment')

    return redirect('checkout')

@csrf_exempt
def sslcommerz_payment_success(request):
    if request.method == 'POST':
        val_id = request.POST.get('val_id')
        status = request.POST.get('status')
        tran_id = request.POST.get('tran_id')
        amount = float(request.POST.get('amount', 0))
        email = request.POST.get('cus_email')

        if status == 'VALID':
            try:
                user = User.objects.get(email=email)
                cart_items = CartItem.objects.filter(user=user, is_paid=False, order__isnull=True)

                if cart_items.exists():
                    order = Order.objects.create(
                        user=user,
                        total_amount=amount,
                        payment_method='sslcommerz',
                        status='Completed'
                    )

                    for item in cart_items:
                        item.order = order
                        item.is_paid = True
                        item.save()

                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            price=item.product.price
                        )

                        item.product.stock_quantity -= item.quantity
                        item.product.save()

                    Payment.objects.create(
                        user=user,
                        order=order,
                        amount=amount,
                        payment_method='sslcommerz',
                        status='Completed',
                        transaction_id=tran_id
                    )

                    return HttpResponse("Payment successful and order created")

            except Exception as e:
                print(e)
                return HttpResponse("Something went wrong", status=500)

    return HttpResponse("Invalid request", status=400)

def calculate_cart_total(user):
    items = CartItem.objects.filter(user=user)
    return sum(item.product.price * item.quantity for item in items)

@login_required
def initiate_sslcommerz_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user, status='Pending')

    if request.method == 'GET':
        payload = {
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'total_amount': float(order.total_amount),
            'currency': 'BDT',
            'tran_id': str(order.id),
            'success_url': request.build_absolute_uri(reverse('sslcommerz_success')),
            'fail_url': request.build_absolute_uri(reverse('sslcommerz_fail')),
            'cancel_url': request.build_absolute_uri(reverse('sslcommerz_cancel')),

            'cus_name': request.user.get_full_name() or 'Customer',
            'cus_email': request.user.email or 'customer@example.com',
            'cus_add1': order.shipping_address or 'Address not provided',
            'cus_city': 'Dhaka',
            'cus_postcode': '1207',
            'cus_country': 'Bangladesh',
            'cus_phone': '01701983377',

            'product_category': 'Electronic',
            'product_name': f"Order #{order.id}",
            'product_profile': 'physical-goods',
            'emi_option': 0,
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; YourAppName/1.0; +https://yourwebsite.com)'
        }

        try:
            response = requests.post(settings.SSLCOMMERZ_API_SESSION_URL, data=payload, headers=headers, timeout=10)
            print(f"Response status code: {response.status_code}")
            print(f"Response text: {response.text}")
            data = response.json()

            if data.get('status') == 'SUCCESS':
                return redirect(data['GatewayPageURL'])
            else:
                return HttpResponse(f"Payment initiation failed: {data.get('failedreason', 'Unknown')}", status=500)
        except Exception as e:
            print(f"Exception during SSLCommerz payment initiation: {e}")
            return HttpResponse(f"Payment initiation exception: {e}", status=500)

    return HttpResponse("Invalid request method", status=405)

@login_required
def payment_success(request):
    tran_id = request.session.get('tran_id')
    order_id = request.session.get('pending_order_id')

    if not order_id:
        return HttpResponse("No order found to process payment. Session data: " + str(list(request.session.items())))

    order = Order.objects.get(id=order_id)

    # Save payment
    Payment.objects.create(
        order=order,
        transaction_id=tran_id,
        amount=order.total_amount,
        status='Completed',
        payment_method='SSLCommerz'
    )

    # Clear session
    request.session.pop('pending_order_id', None)
    request.session.pop('tran_id', None)
    request.session.pop('total', None)
    request.session.pop('cart_item_ids', None)

    return render(request, 'payment_success.html', {'order': order})

@login_required
def payment_fail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Failed'
    order.save()
    messages.error(request, "Payment failed.")
    return redirect('make_payment')

@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Cancelled'
    order.save()
    messages.warning(request, "Payment cancelled.")
    return redirect('cart')

def sslcommerz_api_call(payload):
    sslcommerz_init_url = 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php'  # Use production URL if live
    response = requests.post(sslcommerz_init_url, data=payload)
    if response.status_code == 200:
        return response.json()
    else:
        return {'status': 'FAILED'}

@csrf_exempt
def sslcommerz_success(request):
    # handle success confirmation logic
    return HttpResponse("Payment Success.")

@csrf_exempt
def sslcommerz_fail(request):
    # handle fail confirmation logic
    return HttpResponse("Payment Fail.")

@csrf_exempt
def sslcommerz_cancel(request):
    return HttpResponse("Payment Canceled.")