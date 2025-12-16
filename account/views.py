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
    user = request.user
    copied_traders = CopyTrade.objects.filter(user=user)

    # ----------------------------------------------
    # CHECK FOR EXPIRED TRADES
    # ----------------------------------------------
    open_trades = LiveTrade.objects.filter(user=user, is_open=True)

    for trade in open_trades:
        if trade.closed_at <= timezone.now():  # trade is expired
            
            if trade.profit > 0:
                trade.outcome = "win"
                user.profit += trade.profit
                user.save()
            elif trade.profit < 0:
                trade.outcome = "lost"
                user.profit += trade.profit
                user.save()
            else:
                trade.outcome = "draw"

            # ---- CLOSE TRADE ----
            trade.is_open = False
            trade.save()
            
            messages.info(request, f"You {trade.outcome.lower()}")
            return redirect('home')

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

        if Decimal(amount) > user.current_deposit:
            messages.error(request, "Insufficient balance for this trade.")
            return redirect("home")

        # api_symbol = ticker.replace("/", "")
        # print(api_symbol)
        # api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

        # try:
        #     response = requests.get(api_url, timeout=5)
        #     data = response.json()
        #     print(data)
        #     entry_price = data["price"]
        # except:
        #     messages.error(request, "Failed to fetch price.")
        #     return redirect("home")

        trade = LiveTrade.objects.create(
            user=user,
            category=category,
            ticker=ticker,
            striker=striker,
            interval=interval,
            trade_type=trade_type,
            amount=amount,
            outcome='loss',
            # entry_price=entry_price,
        )

        user = user
        user.current_deposit -= Decimal(amount)
        user.save()

        TradeRecord.objects.create(
            live_trade=trade,
            user=user,
            status='active',
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='completed',
            user=user,
            related_obj=trade,
        )

        telegram(
            f"Hello Admin, {user.username} buy from live trade:"
            f"{trade.category.upper()}.\nGo to admin panel to confirm this."
        )

        messages.success(request, f"Trade opened")
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

        # api_symbol = ticker.replace("/", "")
        # api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

        # try:
        #     response = requests.get(api_url, timeout=5)
        #     data = response.json()
        #     entry_price = data["price"]
        # except:
        #     messages.error(request, "Failed to fetch price.")
        #     return redirect("home")

        trade = LiveTrade.objects.create(
            user=user,
            category=category,
            ticker=ticker,
            striker=striker,
            interval=interval,
            trade_type=trade_type,
            amount=amount,
            outcome='loss',
            # entry_price=entry_price,
        )

        add_transaction(
            type='live_trade',
            amount=amount,
            status='completed',
            user=user,
            related_obj=trade,
        )

        telegram(
            f"Hello Admin, {user.username} just sell from live trade:"
            f"{trade.category.upper()}.\nGo to admin panel to confirm this."
        )

        messages.success(request, f"Trade opened")
        return redirect("home")

    # ----------------------------------------------
    context = {
        'total_balance':user.current_deposit + user.roi_investment + user.copy_expenses + user.profit,
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
    payment_method = PaymentMethod.objects.filter(is_active=True)
    config = Config.objects.first()
    user = request.user

    if request.method == 'POST' and 'bot_purchase' in request.POST:
        amount = config.bot_amount
        method_ref = request.POST.get('currency')
        port_id = request.POST.get('port_id')
        bot_name = request.POST.get('name')

        try:
            portfolio = Portfolio.objects.get(id=port_id)
        except Portfolio.DoesNotExist:
            messages.error(request, "No such portfolio")
            return redirect("invest")
        
        try:
            method = PaymentMethod.objects.get(ref=method_ref)
        except PaymentMethod.DoesNotExist:
            messages.error(request, 'No such payment method')
            return redirect('fund')
        
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            method=method,
            payment_for='bot',
            portfolio=portfolio,
        )

        portfolio.bot_name = bot_name
        portfolio.save()

        add_transaction(
            type='bot',
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
    
    elif request.method == 'POST' and 'withdraw' in request.POST:
        port_id = request.POST.get('port_id')
        withdraw_amount = request.POST.get('withdraw_amount')
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        print(port_id, withdraw_amount, currency, address)

        try:
            portfolio = Portfolio.objects.get(id=port_id, user=user)
        except CopyTrade.DoesNotExist:
            messages.error(request, 'No such portfolio found')
            return redirect('invest')

        if Decimal(withdraw_amount) <= 0:
            messages.error(request, 'Invalid amount entered')
            return redirect('invest')

        if Decimal(withdraw_amount) > portfolio.amount_available:
            messages.error(request, 'Amount exceeds available profit')
            return redirect('invest')

        # Process the withdrawal
        portfolio.amount_available -= Decimal(withdraw_amount)
        portfolio.save()

        # charges = Config.objects.first().withdrawal_charge

        # withdraw = Withdrawal.objects.create(
        #     user = request.user,
        #     wallet_address = address,
        #     amount = withdraw_amount,
        #     name = currency,
        #     withdrawal_type = 'profit',
        #     charges = charges,
        #     available_for_withdraw = Decimal(withdraw_amount) - Decimal(charges)
        # )

        user.profit += Decimal(withdraw_amount)
        user.save()

        # Add transaction record
        add_transaction(
            type='trade',
            amount=withdraw_amount,
            status='completed',
            user=user,
            related_obj=portfolio,
        )

        telegram(
            f"Hello Admin, {user.username} just requested a profit withdrawal of ${withdraw_amount} from investment."
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Withdrawal request submitted successfully')
        return redirect('invest')
    
    elif request.method == 'POST' and 'top' in request.POST:
        trade_id = request.POST.get('port_id')
        top_amount = request.POST.get('amount')

        try:
            portfolio = Portfolio.objects.get(id=trade_id, user=user)
        except CopyTrade.DoesNotExist:
            messages.error(request, 'No such investmment found')
            return redirect('invest')

        if Decimal(top_amount) <= 0:
            messages.error(request, 'Invalid amount entered')
            return redirect('invest')

        if Decimal(top_amount) > user.current_deposit:
            messages.error(request, 'Insufficient balance for this top-up')
            return redirect('invest')

        # Process the top-up
        portfolio.amount_invested += Decimal(top_amount)
        portfolio.save()

        # Deduct from user's current deposit
        user.current_deposit -= Decimal(top_amount)
        user.roi_investment += Decimal(top_amount)
        user.save()

        # Add transaction record
        add_transaction(
            type='trade',
            amount=Decimal(top_amount),
            status='completed',
            user=request.user,
            related_obj=portfolio,
        )

        telegram(
            f"Hello Admin, {user.username} just topped up ${top_amount} to investment."
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, 'Top-up successful')
        return redirect('invest')
    
    context = {
        'body_class':"portfolios-with-data-page",
        'portfolios':portfolios,
        'portfolio_count': portfolios.count(),
        'methods':payment_method,
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
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except InvalidOperation:
            messages.error(request, 'Invalid amount')
            return redirect('profit-withdraw')

        currency = request.POST.get('currency')
        address = request.POST.get('address')

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero')
            return redirect('profit-withdraw')

        config = Config.objects.first()
        if not config:
            messages.error(request, 'System configuration not set')
            return redirect('profit-withdraw')

        charges = Decimal(config.withdrawal_charge)
        total_deduction = amount + charges

        if total_deduction > request.user.profit:
            messages.error(request, 'Low balance')
            return redirect('profit-withdraw')

        # # ✅ CREATE WITHDRAWAL RECORD
        # withdraw = Withdrawal.objects.create(
        #     user=request.user,
        #     wallet_address=address,
        #     amount=amount,
        #     name=currency,
        #     withdrawal_type='profit',
        #     charges=charges,
        #     available_for_withdraw=total_deduction,
        #     status='pending',
        # )

        # # ✅ LOG TRANSACTION
        # add_transaction(
        #     type='withdrawal',
        #     amount=amount,
        #     status='pending',
        #     user=request.user,
        #     related_obj=withdraw,
        # )

        # ✅ NOTIFY ADMIN
        telegram(
            f"🔔 PROFIT WITHDRAWAL REQUEST\n\n"
            f"User: {request.user.username}\n"
            f"Amount: {amount} {currency}\n"
            f"Charges: {charges}\n"
            f"Status: Pending\n\n"
            f"Go to admin panel to confirm."
        )

        new_amount = encode_amount(str(amount))

        return redirect('bill_withdraw', new_amount)

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
def bill_withdraw(request, amount):
    config = Config.objects.first()
    decrypted_amount = decode_amount(amount)
    date = timezone.now()
    charge = (decrypted_amount * request.user.withdrawal_percentage)/100
    context = {
        'config':config,
        'date':date,
        'amount': decrypted_amount,
        'charge':round(charge,2)
    }
    return render(request, 'account/bill_withdraw_from_profit.html', context)

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
    user = request.user
    copied_traders = CopyTrade.objects.filter(user=user)
    if request.method == 'POST' and 'withdraw' in request.POST:
        trade_id = request.POST.get('trader_id')
        withdraw_amount = request.POST.get('withdraw_amount')
        currency = request.POST.get('currency')
        address = request.POST.get('address')

        print(trade_id, withdraw_amount, currency, address)

        try:
            copy_trade = CopyTrade.objects.get(id=trade_id, user=user)
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
        print(type(copy_trade.current_profit), type(Decimal(withdraw_amount)))
        print(copy_trade.current_profit, Decimal(withdraw_amount))
        print(copy_trade.current_profit - Decimal(withdraw_amount))
        print(copy_trade.current_profit + Decimal(withdraw_amount))

        copy_trade.current_profit -= Decimal(withdraw_amount)
        copy_trade.save()

        # charges = Config.objects.first().withdrawal_charge

        # withdraw = Withdrawal.objects.create(
        #     user = request.user,
        #     wallet_address = address,
        #     amount = withdraw_amount,
        #     name = currency,
        #     withdrawal_type = 'profit',
        #     charges = charges,
        #     available_for_withdraw = Decimal(withdraw_amount) - Decimal(charges)
        # )

        user.profit += Decimal(withdraw_amount)
        user.save()

        # Add transaction record
        add_transaction(
            type='trade',
            amount=withdraw_amount,
            status='completed',
            user=user,
            related_obj=copy_trade,
        )

        telegram(
            f"Hello Admin, {user.username} just requested a profit withdrawal of ${withdraw_amount} from copying trader {copy_trade.trader.name}."
            f"\nGo to admin panel to confirm this."
        )

        messages.success(request, f'Withdrawal request submitted successfully')
        return redirect('trades')
    
    elif request.method == 'POST' and 'top' in request.POST:
        trade_id = request.POST.get('trader_id')
        top_amount = request.POST.get('top_amount')

        try:
            copy_trade = CopyTrade.objects.get(id=trade_id, user=user)
        except CopyTrade.DoesNotExist:
            messages.error(request, 'No such trade found')
            return redirect('trades')

        if Decimal(top_amount) <= 0:
            messages.error(request, 'Invalid amount entered')
            return redirect('trades')

        if Decimal(top_amount) > user.current_deposit:
            messages.error(request, 'Insufficient balance for this top-up')
            return redirect('trades')

        # Process the top-up
        copy_trade.amount_copying += Decimal(top_amount)
        copy_trade.save()

        # Deduct from user's current deposit
        user.current_deposit -= Decimal(top_amount)
        user.copy_expenses += Decimal(top_amount)
        user.save()

        # Add transaction record
        add_transaction(
            type='trade',
            amount=Decimal(top_amount),
            status='completed',
            user=request.user,
            related_obj=copy_trade,
        )

        telegram(
            f"Hello Admin, {user.username} just topped up ${top_amount} to copying trader {copy_trade.trader.name}."
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
    # Fetch only verified traders the user is NOT copying
    traders = Trader.objects.filter(
        verified=True
    )
    
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
        
        if Decimal(amount) > request.user.current_deposit:
            messages.error(request, "Insufficient funds. Deposit fund and try again")
            return redirect('fund')

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

        user = request.user

        user.copy_expenses += Decimal(amount)
        user.save()

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

        user = request.user
        
        try:
            plan = InvestmentPlan.objects.get(id=ref)
            print(plan)
        except InvestmentPlan.DoesNotExist:
            messages.error(request, 'No such plan')
            return redirect('plan', amount)
        
        if Decimal(decryped_amount) < plan.minimum_investment:
            messages.error(request, 'Invested amount not upto minimum investment')
            return redirect('create-portfolio')
        
        # Deduct balance
        user.current_deposit -= decryped_amount
        user.roi_investment += decryped_amount
        user.save()
        
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