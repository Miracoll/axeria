from decimal import Decimal, InvalidOperation
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from account.models import Config, CopyTrade, InvestmentPlan, KycVerification, MarketCategory, Payment, PaymentMethod, Portfolio, Trader, Transaction, Withdrawal
from account.utils import add_transaction, decode_amount, encode_amount
from utils.decorators import allowed_users

# Create your views here.

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def home(request):
    return render(request, 'account/index.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def fund(request):
    payment_method = PaymentMethod.objects.filter(is_active=True)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method_ref = request.POST.get('currency')

        if not amount or not method_ref:
            messages.error(request, "Please provide both amount and reference.")
            return redirect('fund')
        
        try:
            method = PaymentMethod.objects.get(ref=method_ref)
        except PaymentMethod.DoesNotExist:
            messages.error(request, 'No such payment method')
            return redirect('fund')
        
        add_transaction(
            type='deposit',
            amount=amount,
            status='pending'
        )
        
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            method=method
        )

        messages.success(request, 'Payment added')
        return redirect('invoice', payment.ref)
    
    context = {
        'methods':payment_method
    }

    return render(request, 'account/fund.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def invoice(request, ref):
    payments = Payment.objects.filter(user=request.user)

    try:
        payment = Payment.objects.get(ref=ref)
    except Payment.DoesNotExist:
        messages.error(request, 'No such payment method')
        return redirect('fund')
    
    context = {
        'payment':payment,
        'payments':payments,
    }

    return render(request, 'account/invoice.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def invest(request):
    portfolios = Portfolio.objects.filter(user=request.user)
    context = {
        'body_class':"portfolios-with-data-page",
        'portfolios':portfolios,
        'portfolio_count': portfolios.count()
    }
    return render(request, 'account/portifolios.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def choose_withdrawal(request):
    if request.method == 'POST':
        method = request.POST.get('method')

        if method == 'profits':
            return redirect('profit-withdraw')
        elif method == 'deposit_balance':
            return redirect('balance-withdraw')
        else:
            messages.error(request, 'Invalid selection')
            return redirect('withdraw')
    return render(request, 'account/choose_withdrawal.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def profit_withdrawal(request):

    if request.method == 'POST':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        add_transaction(
            type='withdrawal',
            amount=amount,
            status='pending'
        )

        config = Config.objects.first()

        Withdrawal.objects.create(
            user = request.user,
            wallet_address = address,
            amount = amount,
            name = currency,
            withdrawal_type = 'profit',
            charges = config.withdrawal_charge,
            available_for_withdraw = amount - config.withdrawal_charge
        )

        messages.success(request, 'Request sent')
        return redirect('profit-withdraw')

    return render(request, 'account/withdraw_profit.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def balance_withdrawal(request):

    if request.method == 'POST':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        add_transaction(
            type='withdrawal',
            amount=amount,
            status='pending'
        )

        Withdrawal.objects.create(
            user = request.user,
            wallet_address = address,
            amount = amount,
            name = currency,
            withdrawal_type = 'deposit'
        )

        messages.success(request, 'Request sent')
        return redirect('balance-withdraw')

    return render(request, 'account/withdraw_balance.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def assets(request):
    categories = MarketCategory.objects.prefetch_related("assets")
    
    context = {
        "categories": categories
    }
    return render(request, 'account/assets.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def stock(request):
    return render(request, 'account/stocks.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def trades(request):
    copied_traders = CopyTrade.objects.all()
    context = {
        'copytrades':copied_traders
    }
    return render(request, 'account/trades.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def copy_trader(request):
    # Get all traders the user is already copying (active ones)
    copying_ids = CopyTrade.objects.filter(
        user=request.user,
        is_active=True
    ).values_list('trader_id', flat=True)

    # Fetch only verified traders the user is NOT copying
    traders = Trader.objects.filter(
        verified=True
    ).exclude(id__in=copying_ids)
    
    if request.method == "POST":
        trader_id = request.POST.get("trader_id")
        amount = request.POST.get("amount")

        try:
            trader = Trader.objects.get(id=trader_id)
        except Trader.DoesNotExist:
            messages.error(request, "Trader not found.")
            return redirect("copy_trader")

        # Validate amount
        try:
            amount = float(amount)
        except:
            messages.error(request, "Invalid amount entered.")
            return redirect("copy_trader")

        if amount < float(trader.min_deposit):
            messages.error(request, f"Minimum deposit is ${trader.min_deposit}.")
            return redirect("copy_trader")

        # Create CopyTrade record
        CopyTrade.objects.create(
            user=request.user,
            trader=trader,
            amount_copying=amount,
            trade_progress=0,        # start at 0%
            current_profit=0,        # start at zero
            is_active=True
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='pending'
        )

        messages.success(request, "You have successfully started copying this trader!")
        return redirect("copy_trader")
    
    context = {
        'traders':traders
    }
    return render(request, 'account/copy_traders.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def chart(request):
    return render(request, 'account/charts.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def transactions(request):
    transactions = Transaction.objects.filter(user=request.user)
    context = {
        'transactions':transactions,
    }
    return render(request, 'account/transactions.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def create_portfolio(request):
    if request.method == 'POST':
        raw_amount = request.POST.get('amount', '').strip()
        cleaned_amount = raw_amount.replace(',', '')

        try:
            amount = Decimal(cleaned_amount)
        except InvalidOperation:
            messages.error(request, 'Invalid amount entered')
            return redirect('create-portfolio')

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero')
            return redirect('create-portfolio')

        if request.user.current_deposit < amount:
            messages.error(request, 'Low balance')
            return redirect('create-portfolio')

        # Encode the amount
        encrypted = encode_amount(amount)

        # Redirect with encrypted amount
        return redirect('plan', encrypted)

    return render(request, "account/create_portfolio.html")

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def plan(request, amount):
    plans = InvestmentPlan.objects.all()

    decryped_amount = decode_amount(amount)

    if request.method == 'POST':
        ref = request.POST.get('ref')
        
        try:
            plan = InvestmentPlan.objects.get(id=ref)
            print(plan)
        except InvestmentPlan.DoesNotExist:
            messages.error(request, 'No such plan')
            return redirect('plan', amount)
        
        # Deduct balance
        request.user.current_deposit -= decryped_amount
        request.user.save()
        
        Portfolio.objects.create(
            user=request.user,
            plan=plan,
            amount_invested = decryped_amount,
        )

        messages.success(request, "Successful")
        return redirect('invest')

    context = {
        'plans':plans
    }
    return render(request, 'account/plan.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def kyc(request):
    if request.method == "POST":
        kyc_file = request.FILES.get('kyc')

        if not kyc_file:
            messages.error(request, "Please upload a valid document.")
            return redirect('kyc')

        # Check if KYC already exists
        try:
            kyc_record = KycVerification.objects.get(user=request.user)

            # Update document
            kyc_record.document = kyc_file
            kyc_record.status = 'pending'   # reset status so admin can review again
            kyc_record.save()

            messages.success(request, "KYC document updated successfully. Awaiting approval.")

        except KycVerification.DoesNotExist:
            # Create a new one
            KycVerification.objects.create(
                user=request.user,
                document=kyc_file,
            )

            messages.success(request, "KYC document submitted successfully. Awaiting approval.")

        return redirect('kyc')

    # GET request (show page)
    try:
        kyc_data = KycVerification.objects.get(user=request.user)
    except KycVerification.DoesNotExist:
        kyc_data = None

    context = {
        'kyc_data': kyc_data
    }
    return render(request, 'account/kyc.html', context)

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def profile(request):
    user = request.user

    if 'update' in request.POST:
        username = request.POST.get("username")
        full_name = request.POST.get("fullName")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        city = request.POST.get("city")
        zip_code = request.POST.get("zip")
        language = request.POST.get("language")

        # Update user fields
        # user.username = username
        user.full_name = full_name
        user.mobile = phone
        user.address = address
        user.city = city
        user.zip_code = zip_code
        user.language = 'en'

        user.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("profile")
    
    elif 'deactivate' in request.POST:
        user.delete()

        messages.success(request, 'Removed')
        return redirect('logout')
    context = {
        'body_class':'profile-page'
    }
    return render(request, 'account/profile.html', context)