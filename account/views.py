from decimal import Decimal, InvalidOperation
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import requests

from account.models import Config, CopyTrade, InvestmentPlan, KycVerification, LiveTrade, MarketCategory, Payment, PaymentMethod, Portfolio, TradeRecord, Trader, Transaction, Withdrawal
from account.utils import add_transaction, decode_amount, encode_amount, telegram
from utils.decorators import allowed_users

# Create your views here.

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def home(request):
    copied_traders = CopyTrade.objects.filter(user=request.user, is_active=True)

    # ----------------------------------------------
    # CHECK FOR EXPIRED TRADES
    # ----------------------------------------------
    open_trades = LiveTrade.objects.filter(user=request.user, is_open=True)

    for trade in open_trades:
        if trade.closed_at <= timezone.now():  # trade is expired
            # Fetch exit price from API
            api_symbol = trade.ticker.replace("/", "")
            api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

            try:
                response = requests.get(api_url, timeout=5)
                data = response.json()
                exit_price = data.get("price", None)
            except:
                exit_price = None  # fallback

            # Close the trade
            trade.exit_price = exit_price
            trade.is_open = False
            trade.save()

    # ----------------------------------------------
    # BUY REQUEST
    # ----------------------------------------------
    if request.method == "POST" and "buy" in request.POST:
        category = request.POST.get("category")
        ticker = request.POST.get("ticker")
        striker = request.POST.get("striker")
        interval = request.POST.get("interval")
        trade_type = "buy"
        amount = request.POST.get("amount")

        if not all([category, ticker, striker, interval, trade_type, amount]):
            messages.error(request, "All fields are required.")
            return redirect("home")

        if Decimal(amount) <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect("home")

        if Decimal(amount) > request.user.current_deposit:
            messages.error(request, "Insufficient balance for this trade.")
            return redirect("home")

        api_symbol = ticker.replace("/", "")
        api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

        try:
            response = requests.get(api_url, timeout=5)
            data = response.json()
            entry_price = data["price"]
        except:
            messages.error(request, "Failed to fetch price.")
            return redirect("home")

        trade = LiveTrade.objects.create(
            user=request.user,
            category=category,
            ticker=ticker,
            striker=striker,
            interval=interval,
            trade_type=trade_type,
            amount=amount,
            entry_price=entry_price,
        )

        user = request.user
        user.current_deposit -= Decimal(amount)
        user.save()

        TradeRecord.objects.create(
            live_trade=trade,
            user=request.user,
            status='active',
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='completed',
            user=request.user,
            related_obj=trade,
        )

        telegram(
            f"Hello Admin, {request.user.username} buy from live trade:"
            f"{trade.category.upper()}.\nGo to admin panel to confirm this."
        )

        messages.success(request, f"Trade opened at {entry_price}! Ref: {trade.ref}")
        return redirect("home")

    # ----------------------------------------------
    # SELL REQUEST
    # ----------------------------------------------
    if request.method == "POST" and "sell" in request.POST:
        category = request.POST.get("category")
        ticker = request.POST.get("ticker")
        striker = request.POST.get("striker")
        interval = request.POST.get("interval")
        trade_type = "sell"
        amount = request.POST.get("amount")

        if not all([category, ticker, striker, interval, trade_type, amount]):
            messages.error(request, "All fields are required.")
            return redirect("home")

        api_symbol = ticker.replace("/", "")
        api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

        try:
            response = requests.get(api_url, timeout=5)
            data = response.json()
            entry_price = data["price"]
        except:
            messages.error(request, "Failed to fetch price.")
            return redirect("home")

        trade = LiveTrade.objects.create(
            user=request.user,
            category=category,
            ticker=ticker,
            striker=striker,
            interval=interval,
            trade_type=trade_type,
            amount=amount,
            entry_price=entry_price,
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='completed',
            user=request.user,
            related_obj=trade,
        )

        telegram(
            f"Hello Admin, {request.user.username} just sell from live trade:"
            f"{trade.category.upper()}.\nGo to admin panel to confirm this."
        )

        messages.success(request, f"Trade opened at {entry_price}! Ref: {trade.ref}")
        return redirect("home")

    # ----------------------------------------------
    context = {
        'copied_traders': copied_traders,
        'open_trades': open_trades,
    }
    return render(request, 'account/index.html', context)

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
        
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            method=method
        )

        add_transaction(
            type='deposit',
            amount=amount,
            status='pending',
            user=request.user,
            related_obj=payment,
        )

        telegram(
            f"Hello Admin, {request.user.username} just fund his/her account with {amount}"
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Payment invoice created.\nPlease complete the payment.')
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

        config = Config.objects.first()
        charges = Decimal(config.withdrawal_charge)

        if (amount + charges) > request.user.profit:
            messages.error(request, 'Low balance')
            return redirect('profit-withdraw')

        withdraw = Withdrawal.objects.create(
            user = request.user,
            wallet_address = address,
            amount = amount,
            name = currency,
            withdrawal_type = 'profit',
            charges = config.withdrawal_charge,
            available_for_withdraw = amount + config.withdrawal_charge
        )

        add_transaction(
            type='withdrawal',
            amount=amount,
            status='pending',
            user=request.user,
            related_obj=withdraw,
        )

        telegram(
            f"Hello Admin, {request.user.username} just placed a profit withdrawal"
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Request sent')
        return redirect('profit-withdraw')

    return render(request, 'account/withdraw_profit.html')

@login_required(login_url='login')
@allowed_users(allowed_roles=['admin', 'trader'])
def balance_withdrawal(request):

    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        config = Config.objects.first()
        charges = Decimal(config.withdrawal_charge)

        if (amount + charges) > request.user.current_deposit:
            messages.error(request, 'Low balance')
            return redirect('balance-withdraw')

        withdraw = Withdrawal.objects.create(
            user=request.user,
            wallet_address=address,
            amount=amount,
            name=currency,
            withdrawal_type='deposit',
            charges=charges,
            available_for_withdraw=amount + charges
        )

        # Add transaction linked to this withdrawal
        add_transaction(
            type='withdrawal',
            amount=amount,
            status='pending',
            user=request.user,
            related_obj=withdraw,
        )

        # Notify admin
        telegram(
            f"Hello Admin, {request.user.username} just placed a balance withdrawal"
            f"\nGo to admin panel to confirm this."
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
    copied_traders = CopyTrade.objects.filter(user=request.user, is_active=True)
    if request.method == 'POST' and 'withdraw' in request.POST:
        trade_id = request.POST.get('trader_id')
        withdraw_amount = request.POST.get('withdraw_amount')
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        print(trade_id, withdraw_amount, currency, address)

        try:
            copy_trade = CopyTrade.objects.get(id=trade_id, user=request.user)
        except CopyTrade.DoesNotExist:
            messages.error(request, 'No such trade found')
            return redirect('trades')

        if Decimal(withdraw_amount) <= 0:
            messages.error(request, 'Invalid amount entered')
            return redirect('trades')

        if Decimal(withdraw_amount) > copy_trade.current_profit:
            messages.error(request, 'Amount exceeds available profit')
            return redirect('trades')

        # Process the withdrawal
        # copy_trade.current_profit -= Decimal(withdraw_amount)
        # copy_trade.save()

        charges = Config.objects.first().withdrawal_charge

        withdraw = Withdrawal.objects.create(
            user = request.user,
            wallet_address = address,
            amount = withdraw_amount,
            name = currency,
            withdrawal_type = 'profit',
            charges = charges,
            available_for_withdraw = Decimal(withdraw_amount) - Decimal(charges)
        )

        # Add transaction record
        add_transaction(
            type='withdrawal',
            amount=withdraw_amount,
            status='pending',
            user=request.user,
            related_obj=withdraw,
        )

        telegram(
            f"Hello Admin, {request.user.username} just requested a profit withdrawal of ${withdraw_amount} from copying trader {copy_trade.trader.name}."
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Withdrawal request submitted successfully')
        return redirect('trades')
    
    elif request.method == 'POST' and 'top' in request.POST:
        trade_id = request.POST.get('trader_id')
        top_amount = request.POST.get('top_amount')

        try:
            copy_trade = CopyTrade.objects.get(id=trade_id, user=request.user)
        except CopyTrade.DoesNotExist:
            messages.error(request, 'No such trade found')
            return redirect('trades')

        if Decimal(top_amount) <= 0:
            messages.error(request, 'Invalid amount entered')
            return redirect('trades')

        if Decimal(top_amount) > request.user.current_deposit:
            messages.error(request, 'Insufficient balance for this top-up')
            return redirect('trades')

        # Process the top-up
        copy_trade.amount_copying += Decimal(top_amount)
        copy_trade.save()

        # Deduct from user's current deposit
        request.user.current_deposit -= Decimal(top_amount)
        request.user.save()

        telegram(
            f"Hello Admin, {request.user.username} just topped up ${top_amount} to copying trader {copy_trade.trader.name}."
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Top-up successful')
        return redirect('trades')
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
            return redirect("copy-trader")

        # Validate amount
        try:
            amount = float(amount)
        except:
            messages.error(request, "Invalid amount entered.")
            return redirect("copy-trader")

        if amount < float(trader.min_deposit):
            messages.error(request, f"Minimum deposit is ${trader.min_deposit}.")
            return redirect("copy-trader")

        # Create CopyTrade record
        trade = CopyTrade.objects.create(
            user=request.user,
            trader=trader,
            amount_copying=amount,
            trade_progress=0,        # start at 0%
            current_profit=0,        # start at zero
            is_active=False
        )

        telegram(
            f"Hello Admin, {request.user.username} just copied a trader:"
            f"{trader.name}.\nGo to admin panel to confirm this."
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='pending',
            user=request.user,
            related_obj=trade,
        )

        messages.success(request, "You have successfully started copying this trader!")
        return redirect("copy-trader")
    
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

        telegram(
            f"Hello Admin, {request.user.username} just started an investment"
            f"\nGo to admin panel to confirm this."
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

            telegram(
                f"Hello Admin, {request.user.username} just uploaded his/her kyc document:"
                f"\nGo to admin panel to confirm this."
            )

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

        telegram(
            f"Hello Admin, {request.user.username} just updated his/her profile:"
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, "Profile updated successfully!")
        return redirect("profile")
    
    elif 'deactivate' in request.POST:
        user.delete()

        telegram(
            f"Hello Admin, {request.user.username} just deleted his/her acocunt:"
        )

        messages.success(request, 'Removed')
        return redirect('logout')
    context = {
        'body_class':'profile-page'
    }
    return render(request, 'account/profile.html', context)