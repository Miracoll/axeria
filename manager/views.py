from decimal import Decimal, InvalidOperation
from io import BytesIO
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mass_mail, send_mail
from django.contrib.auth import update_session_auth_hash
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import qrcode
import requests
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from account.models import Config, CopyTrade, IPAddress, InvestmentPlan, KycVerification, LiveTrade, Payment, PaymentMethod, Portfolio, Trader, Transaction, User, Withdrawal
from account.utils import add_transaction
from utils.decorators import allowed_users

# Create your views here.

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def home(request):
    total_deposit = Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    trader_count = User.objects.filter(groups__name='trader').count()
    deactivated_users_count = User.objects.filter(is_active=False, groups__name='trader').count()
    blocked_users_count = User.objects.filter(block=True, groups__name='trader').count()
    payments = Payment.objects.filter(status='pending')
    active_portfolios = Portfolio.objects.filter(status='active')
    ip_addresses = IPAddress.objects.all()
    context = {
        'total_deposit':total_deposit,
        'trader_count':trader_count,
        'deactivated_users_count':deactivated_users_count,
        'blocked_users_count':blocked_users_count,
        'payments':payments,
        'active_portfolios':active_portfolios,
        'ip_addresses': ip_addresses,
    }
    return render(request, 'manager/index.html', context)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def approve_payment(request):
    if request.method == "POST":
        payment_id = request.POST.get("id")

        try:
            p = Payment.objects.get(id=payment_id)
            p.status = "completed"
            p.save()

            u = User.objects.get(id=p.user.id)
            u.current_deposit += p.amount
            u.save()

            # ✅ Update corresponding Transaction if it exists
            transaction = Transaction.objects.filter(
                content_type=ContentType.objects.get_for_model(Payment),
                object_id=p.id
            ).first()

            if p.payment_for == 'bot':
                p.portfolio.bot_active = True
                p.portfolio.save()

            transaction.status = "completed"  # update status
            transaction.save()
            
            return JsonResponse({"status": "success"})
        except LiveTrade.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Payment not found"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def decline_payment(request):
    if request.method == "POST":
        payment_id = request.POST.get("id")

        try:
            p = Payment.objects.get(id=payment_id)
            p.status = "failed"
            p.save()

            # ✅ Update corresponding Transaction if it exists
            transaction = Transaction.objects.filter(
                content_type=ContentType.objects.get_for_model(Payment),
                object_id=p.id
            ).first()

            transaction.status = "completed"  # update status
            transaction.save()
            
            return JsonResponse({"status": "success"})
        except LiveTrade.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Payment not found"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def withdrawal(request):
    withdraws = Withdrawal.objects.all().order_by('-created_on')

    context = {
        'withdraws':withdraws,
    }
    return render(request, 'manager/withdrawal.html', context)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def approve_withdrawal(request):
    if request.method == "POST":
        payment_id = request.POST.get("id")

        try:
            w = Withdrawal.objects.get(id=payment_id)
            w.status = "approved"
            w.save()

            u = User.objects.get(id=w.user.id)
            u.current_deposit -= w.amount
            u.save()

            # ✅ Update corresponding Transaction if it exists
            transaction = Transaction.objects.filter(
                content_type=ContentType.objects.get_for_model(Withdrawal),
                object_id=w.id
            ).first()

            transaction.status = "completed"  # update status
            transaction.save()
            
            return JsonResponse({"status": "success"})
        except LiveTrade.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Withdrawal not found"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def decline_withdrawal(request):
    if request.method == "POST":
        payment_id = request.POST.get("id")

        try:
            w = Withdrawal.objects.get(id=payment_id)
            w.status = "rejected"
            w.save()

            # ✅ Update corresponding Transaction if it exists
            transaction = Transaction.objects.filter(
                content_type=ContentType.objects.get_for_model(Withdrawal),
                object_id=w.id
            ).first()

            transaction.status = "completed"  # update status
            transaction.save()
            
            return JsonResponse({"status": "success"})
        except LiveTrade.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Withdrawal not found"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def create_trader(request):
    if request.method == "POST":
        name = request.POST.get("name")
        min_deposit = request.POST.get("min")
        period = request.POST.get("period")
        duration = request.POST.get("duration")
        trading_fee = request.POST.get("trade_fee")
        roi = request.POST.get("roi")
        total_investors = request.POST.get("investors")
        active_investors = request.POST.get("active")
        risk = request.POST.get("risk")
        win_rate = request.POST.get("rate")
        image = request.FILES.get("image")

        # Validate required fields
        if not name or not min_deposit or not duration:
            messages.error(request, "Name, Minimum Deposit, and Duration are required.")
            return redirect("admin-create-trader")

        # Convert min deposit
        try:
            min_deposit = Decimal(min_deposit)
        except InvalidOperation:
            messages.error(request, "Invalid minimum deposit.")
            return redirect("admin-create-trader")

        # Convert trading fee
        try:
            trading_fee = Decimal(trading_fee)
        except InvalidOperation:
            trading_fee = 10  # default

        # Convert ROI
        try:
            roi = Decimal(roi)
        except InvalidOperation:
            roi = 0

        # Convert risk and win rate
        try:
            risk = Decimal(risk)
        except InvalidOperation:
            risk = 0

        try:
            win_rate = Decimal(win_rate)
        except InvalidOperation:
            win_rate = 0

        # Convert duration into weeks
        try:
            duration = int(duration)
        except ValueError:
            messages.error(request, "Invalid duration value.")
            return redirect("admin-create-trader")

        if period == "days":
            duration_weeks = duration / 7
        elif period == "weeks":
            duration_weeks = duration
        elif period == "months":
            duration_weeks = duration * 4
        else:
            messages.error(request, "Invalid duration period.")
            return redirect("admin-create-trader")

        # Save trader
        trader = Trader.objects.create(
            name=name,
            min_deposit=min_deposit,
            duration_weeks=duration_weeks,
            trading_fee_percentage=trading_fee,
            daily_roi=roi,
            total_investors=total_investors or 0,
            active_investors=active_investors or 0,
            risk_level=risk,
            win_rate=win_rate,
        )

        # Save image if uploaded
        if image:
            trader.image = image
            trader.save()

        messages.success(request, "Trader created successfully!")
        return redirect("admin-create-trader")

    return render(request, "manager/create_trader.html")

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def expert(request):
    traders = Trader.objects.all()
    if request.method == "POST" and "edit-expert" in request.POST:
        trader_id = request.POST.get("id")
        t = Trader.objects.get(id=trader_id)

        t.name = request.POST.get("name")
        t.min_deposit = request.POST.get("min")
        t.duration_weeks = request.POST.get("duration")
        t.trading_fee_percentage = request.POST.get("trade_fee")
        t.daily_roi = request.POST.get("roi")
        t.total_investors = request.POST.get("investors")
        t.active_investors = request.POST.get("active")
        t.risk_level = request.POST.get("risk")
        t.win_rate = request.POST.get("rate")

        t.save()

        messages.success(request, 'Update successful')
        return redirect("admin-experts")
    
    elif request.method == "POST" and "delete-expert" in request.POST:
        trader_id = request.POST.get("id")
        t = Trader.objects.get(id=trader_id)

        t.delete()

        messages.success(request, 'Expert removed')
        return redirect('admin-experts')

    return render(request, 'manager/experts.html', {"traders": traders})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])

def edit_users(request):
    if request.method == "POST" and "update" in request.POST:
        user_id = request.POST.get("user_id")
        try:
            u = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User does not exist")
            return redirect("admin-edit-user")
        
        # Update user fields
        u.first_name = request.POST.get("fname", u.first_name)
        u.last_name = request.POST.get("lname", u.last_name)
        u.email = request.POST.get("email", u.email)
        
        u.mobile = request.POST.get("phone", u.mobile)
        u.current_deposit = request.POST.get("main_bal", u.current_deposit)
        u.profit = request.POST.get("profit", u.profit)
        u.custom_message = request.POST.get("custom_message", u.custom_message)
        u.message_format = request.POST.get("message_format", u.message_format)
        
        # Save user and profile
        u.save()

        messages.success(request, 'Update successful')
        return redirect("admin-edit-user")
    
    elif request.method == "POST" and "suspend" in request.POST:
        user_id = request.POST.get("user_id")
        try:
            u = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User does not exist")
            return redirect("admin-edit-user")
        
        u.block = True
        u.save()

        messages.success(request, 'Done')
        return redirect('admin-edit-user')
    
    elif request.method == "POST" and "unsuspend" in request.POST:
        user_id = request.POST.get("user_id")
        try:
            u = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User does not exist")
            return redirect("admin-edit-user")
        
        u.block = False
        u.save()

        messages.success(request, 'Done')
        return redirect('admin-edit-user')
    
    elif request.method == "POST" and "delete" in request.POST:
        user_id = request.POST.get("user_id")
        try:
            u = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User does not exist")
            return redirect("admin-edit-user")
        
        u.delete()

        messages.success(request, 'Done')
        return redirect('admin-edit-user')

    # Fetch only users in 'trader' group
    users = User.objects.filter(groups__name='trader')
    return render(request, 'manager/edit_users.html', {'users': users})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def manage_trade(request):
    trades = CopyTrade.objects.all().order_by('-opened_date')
    if request.method == "POST":
        trade_id = request.POST.get("trade_id")
        action = request.POST.get("status")
        try:
            trade = CopyTrade.objects.get(id=trade_id)
            if action == "active":
                trade.is_active = True
            elif action == "in-active":
                trade.is_active = False
            trade.save()
            messages.success(request, "Trade status updated successfully.")
            return redirect('admin-manage-trade')
        except CopyTrade.DoesNotExist:
            messages.error(request, "Trade record not found.")
    return render(request, 'manager/manage_trades.html', {'trades':trades})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def user_trade(request, trade_id):
    trade = CopyTrade.objects.get(id=trade_id)
    traders = Trader.objects.all()
    user_trades = LiveTrade.objects.filter(user=trade.user).order_by('-opened_at')
    user = trade.user

    if request.method == "POST" and "create_live_trade" in request.POST:
        ticker = request.POST.get("ticker")
        striker = request.POST.get("striker")
        interval = request.POST.get("interval")
        trade_type = request.POST.get("trade_type")
        amount = request.POST.get("amount")
        expert_id = request.POST.get("expert")
        outcome = request.POST.get("outcome")
        category = request.POST.get("category")

        expert = Trader.objects.get(id=expert_id) if expert_id else None

        print("Creating live trade with:", ticker, striker, interval, trade_type, amount, expert, outcome, category)

        if user.current_deposit < Decimal(amount):
            messages.error(request, "User balance is low")
            return redirect('"admin-user-trade", trade_id=trade_id')

        # if category == "crypto":
        #     api_symbol = ticker.replace("/", "")
        #     api_url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"

        #     try:
        #         response = requests.get(api_url, timeout=5)
        #         data = response.json()
        #         entry_price = data["price"]
        #     except:
        #         messages.error(request, "Failed to fetch price.")
        #         return redirect("admin-user-trade", trade_id=trade_id)
        # else:
        #     try:
        #         stock = yf.Ticker(ticker)
        #         data = stock.history(period="1d")
        #         price = data['Close'].iloc[-1]
        #         entry_price =  price
        #     except Exception as e:
        #         messages.error(request, f"Failed to fetch stock price: {str(e)}")
        #         return redirect("admin-user-trade", trade_id=trade_id)

        user_live_trade = LiveTrade.objects.create(
            user = trade.user,
            ticker = ticker,
            striker = striker,
            interval = interval,
            trade_type = trade_type,
            amount = Decimal(amount),
            trader = expert,
            outcome = outcome,
            # entry_price=entry_price,
            admin_create=True,
        )

        user.current_deposit -= Decimal(amount)
        user.save()

        add_transaction(
            type='live_trade',
            amount=amount,
            status='active',
            user=trade.user,
            related_obj=user_live_trade,
        )

        messages.success(request, "Trade created successfully.")
        return redirect('admin-user-trade', trade_id=trade_id)
    
    elif request.method == "POST" and "edit" in request.POST:
        # ticker = request.POST.get("ticker")
        amount = request.POST.get("amount")
        profit = request.POST.get("profit")
        trade_type = request.POST.get("status")
        trader_id = request.POST.get("trade_id")

        print("Editing live trade ID:", trader_id, "with:", amount, profit, trade_type)

        try:
            live_trade = LiveTrade.objects.get(id=trader_id)
        except LiveTrade.DoesNotExist:
            messages.error(request, "Live trade not found.")
            return redirect('admin-user-trade', trade_id=trade_id)
        
        # live_trade.ticker = ticker
        live_trade.amount = Decimal(amount)
        live_trade.profit = Decimal(profit)
        live_trade.trade_type = True if trade_type == "open" else False
        live_trade.save()

        if live_trade.is_open:
            # ✅ Update corresponding Transaction if it exists
            transaction = Transaction.objects.filter(
                content_type=ContentType.objects.get_for_model(LiveTrade),
                object_id=live_trade.id
            ).first()

            transaction.status = "completed"  # update status
            transaction.save()

        messages.success(request, "Trade updated successfully.")
        return redirect('admin-user-trade', trade_id=trade_id)

    context = {
        'user_trades': user_trades,
        'traders': traders,
        'trade_id': trade_id,
    }
    return render(request, 'manager/user_trade.html', context)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def refresh_user_trade(request, trade_id):
    try:
        user = CopyTrade.objects.get(id=trade_id).user
        trades = LiveTrade.objects.filter(user=user)

        for trade in trades:
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
                return redirect('admin-user-trade', trade_id=trade_id)

        messages.success(request, "Trades refreshed successfully.")
        return redirect('admin-user-trade', trade_id=trade_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('admin-user-trade', trade_id=trade_id)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def delete_trade(request):
    if request.method == "POST":
        trade_id = request.POST.get("id")

        try:
            trade = LiveTrade.objects.get(id=trade_id)
            trade.delete()
            return JsonResponse({"status": "success"})
        except LiveTrade.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Trade not found"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def activate(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        action = request.POST.get("action")
        try:
            user_record = User.objects.get(id=user_id)
            if action == "activate":
                user_record.is_active = True
            elif action == "deactivate":
                user_record.is_active = False
            user_record.save()
        except User.DoesNotExist:
            messages.error(request, "User record not found.")
    users = User.objects.filter(groups__name='trader')
    return render(request, 'manager/activate.html', {'users':users})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def kyc(request):
    if request.method == "POST":
        kyc_id = request.POST.get("kyc_id")
        action = request.POST.get("action")
        try:
            kyc_record = KycVerification.objects.get(id=kyc_id)
            if action == "approve":
                kyc_record.status = "approved"
                kyc_record.rejected_reason = ""
            elif action == "reject":
                kyc_record.status = "rejected"
            kyc_record.save()
        except KycVerification.DoesNotExist:
            messages.error(request, "KYC record not found.")

    kycs = KycVerification.objects.all()
    return render(request, 'manager/kyc.html', {'kycs': kycs})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def edit_portfolio(request):
    portfolios = Portfolio.objects.all().order_by('-setup_date')
    if request.method == "POST":

        # ===== USER =====
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, id=user_id)

        # ===== PORTFOLIO =====
        portfolio_id = request.POST.get("portfolio_id")
        plan_id = request.POST.get("plan_id")
        portfolio = get_object_or_404(Portfolio, id=portfolio_id, user=user)
        plan = get_object_or_404(InvestmentPlan, id=plan_id)

        portfolio.plan = plan
        portfolio.amount_invested = Decimal(request.POST.get("amount_invested", 0))
        portfolio.amount_available = Decimal(request.POST.get("amount_available", 0))
        portfolio.profit = Decimal(request.POST.get("portfolio_profit", 0))
        portfolio.status = request.POST.get("status")
        portfolio.bot_active = True if request.POST.get("bot_active") else False
        portfolio.bot_name = request.POST.get("bot_name")

        portfolio.save()

        messages.success(request, "Client and portfolio updated successfully")
        return redirect("admin-edit-portfolio")
    
    context = {
        'portfolios':portfolios,
        "plans": InvestmentPlan.objects.all(),
    }
    return render(request, 'manager/edit_portifolios.html', context)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def active_trade(request):
    trades = CopyTrade.objects.filter(is_active=True).order_by('-opened_date')
    return render(request, 'manager/active.html',{'trades':trades})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def newsletter(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        # Get users in "trader" group
        traders = User.objects.filter(groups__name='trader').exclude(email='')
        email_list = [u.email for u in traders]

        if not email_list:
            messages.error(request, "No trader users have valid email addresses.")
            return render(request, 'manager/newsletter.html')

        # Prepare messages for bulk sending
        messages_to_send = []
        for email in email_list:
            messages_to_send.append(
                (subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            )

        # Send bulk email
        send_mass_mail(messages_to_send, fail_silently=False)

        messages.success(request, "Newsletter sent successfully!")
        return redirect('admin-newsletter')

    return render(request, 'manager/newsletter.html')

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def message(request):
    traders = User.objects.filter(groups__name='trader')

    if request.method == 'POST':
        title = request.POST.get('title')
        html_message = request.POST.get('message')   # Quill HTML
        email = request.POST.get('email')

        if not title or not html_message or not email:
            messages.error(request, "All fields are required.")
            return redirect('admin-message')

        try:
            # Convert HTML → plain text version
            text_message = strip_tags(html_message)

            msg = EmailMultiAlternatives(
                subject=title,
                body=text_message,         # plain text version
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_message, "text/html")  # HTML version
            msg.send()

            messages.success(request, "Message sent successfully!")

        except Exception as e:
            messages.error(request, f"Failed to send email: {e}")

        return redirect('admin-message')

    return render(request, 'manager/messages.html', {'traders': traders})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def change_password(request):
    if request.method == "POST":
        current_password = request.POST.get("password")
        new_password = request.POST.get("newPassword")
        confirm_password = request.POST.get("confirmPassword")

        user = request.user

        # Check current password
        if not user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect('admin-change-password')

        # Check match
        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect('admin-change-password')

        # Optional: Enforce minimum password length
        if len(new_password) < 6:
            messages.error(request, "New password must be at least 6 characters.")
            return redirect('admin-change-password')

        # Save new password
        user.set_password(new_password)
        user.save()

        # Keep user logged in after password change
        update_session_auth_hash(request, user)

        messages.success(request, "Password changed successfully.")
        return redirect("admin-change-password")

    return render(request, 'manager/change_password.html')

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def change_username(request):
    if request.method == "POST":
        new_username = request.POST.get("uname")

        # Empty field check
        if not new_username:
            messages.error(request, "Username cannot be empty.")
            return redirect("admin-change-username")

        # Username already exists?
        if User.objects.filter(username=new_username).exclude(id=request.user.id).exists():
            messages.error(request, "This username is already taken.")
            return redirect("admin-change-username")

        # Update username
        user = request.user
        user.username = new_username
        user.save()

        messages.success(request, "Username updated successfully.")
        return redirect("admin-change-username")

    return render(request, 'manager/change_username.html')

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def change_email(request):
    if request.method == "POST":
        new_email = request.POST.get("email")

        # Empty field check
        if not new_email:
            messages.error(request, "Email cannot be empty.")
            return redirect("admin-change-email")

        # Email already exists?
        if User.objects.filter(email=new_email).exists():
            messages.error(request, "This email is already taken.")
            return redirect("admin-change-email")

        # Update username
        user = request.user
        user.email = new_email
        user.save()

        messages.success(request, "Username updated successfully.")
        return redirect("admin-change-email")
    return render(request, 'manager/change_email.html')

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def site_info(request):
    config = Config.objects.first()

    if request.method == "POST":
        email = request.POST.get("email")
        sitename = request.POST.get("sitename")
        phone = request.POST.get("phone")

        # Validate fields
        if not email or not sitename or not phone:
            messages.error(request, "All fields are required.")
            return redirect("admin-site-info")

        # Update database
        config.email = email
        config.site_name = sitename
        config.site_mobile = phone
        config.save()

        messages.success(request, "Site information updated successfully.")
        return redirect("admin-site-info")

    return render(request, 'manager/site_info.html', {'config': config})


@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def plans(request):
    if request.method == "POST" and "create-plan" in request.POST:

        try:
            name = request.POST.get("newplanname")
            plan_type = request.POST.get("newtype")
            recurring_days = int(request.POST.get("newrecurring"))
            min_amount = request.POST.get("newamount")
            max_amount = request.POST.get("newmaxamount")
            roi = request.POST.get("newroi")
            trade_fee = request.POST.get("trade_fee")
            term = int(request.POST.get("newterm"))
            duration = int(request.POST.get("newduration"))  # 1,7,30

            if float(max_amount) < float(min_amount):
                messages.error(request, "Maximum amount cannot be less than minimum amount.")
                return redirect("manager-plans")

            InvestmentPlan.objects.create(
                name=name,
                plan_type=plan_type,
                recurring_days=recurring_days,
                minimum_investment=min_amount,
                maximum_investment=max_amount,
                percentage=roi,
                trade_fee=trade_fee,
                term=term,
                duration_multiplier=duration
            )

            messages.success(request, "Investment plan created successfully!")
            return redirect("admin-plans")

        except Exception as e:
            messages.error(request, f"Error creating plan: {e}")
            return redirect("admin-plans")
        
    elif request.method == "POST" and "edit" in request.POST:
        try:
            plan_id = request.POST.get("plan_id")
            plan = get_object_or_404(InvestmentPlan, id=plan_id)

            plan.name = request.POST.get("pname")
            plan.plan_type = request.POST.get("type")
            plan.recurring_days = int(request.POST.get("recurring"))
            plan.percentage = request.POST.get("roi")
            plan.trade_fee = request.POST.get("trade_fee")
            plan.term = int(request.POST.get("term"))
            duration_multiplier = int(request.POST.get("duration"))
            plan.duration_multiplier = duration_multiplier
            plan.minimum_investment = request.POST.get("amount")
            plan.maximum_investment = request.POST.get("maxamount")

            # Active status
            active_val = request.POST.get("active")
            if active_val == "yes":
                plan.is_active = True
            elif active_val == "no":
                plan.is_active = False

            plan.save()
            messages.success(request, "Investment plan updated successfully!")
            return redirect("admin-plans")

        except Exception as e:
            messages.error(request, f"Error updating plan: {e}")
            return redirect("admin-plans")
        
    elif request.method == "POST" and "delete" in request.POST:
        try:
            plan_id = request.POST.get("plan_id")
            plan = get_object_or_404(InvestmentPlan, id=plan_id)

            plan.delete()
            messages.success(request, "Investment plan removed successfully!")
            return redirect("admin-plans")

        except Exception as e:
            messages.error(request, f"Error deleting plan: {e}")
            return redirect("admin-plans")

    # GET: Show plans
    plans = InvestmentPlan.objects.all()
    return render(request, 'manager/plans.html', {'plans': plans})

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def payments(request):
    if request.method == "POST" and "create_payment" in request.POST:
        name = request.POST.get("create_name")
        wallet_address = request.POST.get("address")

        if not name or not wallet_address:
            messages.error(request, "Name and Wallet Address are required.")
            return redirect("admin-payments")
        
        try:
            # Generate QR code image for wallet address
            qr_img = qrcode.make(wallet_address)

            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            qr_file = ContentFile(buffer.getvalue(), f"{name}_qrcode.png")

            # Save PaymentMethod
            PaymentMethod.objects.create(
                name=name,
                wallet_address=wallet_address,
                qrcode=qr_file,
                is_active=True
            )

            messages.success(request, "Payment method created successfully with QR code!")
            return redirect("admin-payments")

        except Exception as e:
            messages.error(request, f"Error creating payment method: {e}")
            return redirect("admin-payments")
        
    elif request.method == "POST" and "update_payment" in request.POST:
        payment_id = request.POST.get("payment_id")
        name = request.POST.get("create_name")
        wallet_address = request.POST.get("address")
        active = request.POST.get("active", "yes")

        if not payment_id:
            messages.error(request, "Payment ID is required for update.")
            return redirect("admin-payments")

        if not name or not wallet_address:
            messages.error(request, "Name and Wallet Address are required.")
            return redirect("admin-payments")

        try:
            # Fetch the existing PaymentMethod
            payment = PaymentMethod.objects.get(id=payment_id)

            # Update fields
            payment.name = name
            payment.wallet_address = wallet_address
            payment.is_active = True if active.lower() == "yes" else False

            # Generate new QR code for updated wallet address
            qr_img = qrcode.make(wallet_address)
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            qr_file = ContentFile(buffer.getvalue(), f"{name}_qrcode.png")
            payment.qrcode.save(f"{name}_qrcode.png", qr_file, save=False)

            payment.save()  # Save all updates
            messages.success(request, "Payment method updated successfully with QR code!")
            return redirect("admin-payments")

        except PaymentMethod.DoesNotExist:
            messages.error(request, "Payment method not found.")
            return redirect("admin-payments")
        except Exception as e:
            messages.error(request, f"Error updating payment method: {e}")
            return redirect("admin-payments")

    # GET request
    payment_methods = PaymentMethod.objects.all()
    context = {'payment_methods': payment_methods}
    return render(request, 'manager/payments.html', context)

@login_required(login_url='admin_login')
@allowed_users(allowed_roles=['admin'])
def update_config(request):
    config = Config.objects.first()

    # If config does not exist, create one
    if not config:
        config = Config.objects.create()

    if request.method == 'POST':
        email = request.POST.get('email')
        bot_amount = request.POST.get('bot_amount')

        # Update fields
        config.email = email
        config.bot_amount = bot_amount

        config.save()

        messages.success(request, "Configuration updated successfully.")
        return redirect('admin-config')

    context = {
        'config': config
    }
    return render(request, 'manager/config.html', context)

def admin_login(request):
    return render(request, 'manager/login.html')