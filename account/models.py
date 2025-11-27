from decimal import Decimal
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.text import slugify

# Create your models here.

class Config(models.Model):
    withdrawal_charge = models.FloatField()
    email = models.CharField(max_length=50, blank=True, null=True)
    site_name = models.CharField(max_length=50, blank=True, null=True)
    site_mobile = models.CharField(max_length=50, blank=True, null=True)

class User(AbstractUser):
    FORMAT_CHOICES = [
        ('popup', 'popup'),
        ('message', 'message'),
    ]
    mobile = models.CharField(max_length=15)
    current_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    roi_investment = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    copy_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    block = models.BooleanField(default=False)
    psw = models.CharField(max_length=100, blank=True, null=True)
    custom_message = models.CharField(max_length=300, blank=True, null=True)
    message_format = models.CharField(max_length=100, blank=True, null=True, choices=FORMAT_CHOICES)

class Trader(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="traders/", default="default.png")

    # Duration (weeks or days)
    duration_weeks = models.IntegerField(help_text="Duration in weeks")

    # Trading metrics
    total_investors = models.IntegerField(default=0)
    active_investors = models.IntegerField(default=0)
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    risk_level = models.DecimalField(max_digits=10, decimal_places=1, help_text="e.g. 2.2")
    win_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="e.g. 95 (%)")

    # ROI and trading fee
    daily_roi = models.DecimalField(max_digits=10, decimal_places=2)  
    trading_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10)

    verified = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def duration_days(self):
        """Convert weeks to days (used by CopyTrade model)"""
        return self.duration_weeks * 7

class CopyTrade(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='copy_trades')
    trader = models.ForeignKey(Trader, on_delete=models.CASCADE, related_name='copies')

    amount_copying = models.DecimalField(max_digits=12, decimal_places=2)
    opened_date = models.DateTimeField(auto_now_add=True)

    # Runtime fields
    trade_progress = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    def calculate_profit(self):
        """
        Calculates current profit based on:
        amount_copying * (daily_roi/100) * (estimated_days)
        """
        roi_per_day = Decimal(self.trader.daily_roi) / Decimal(100)
        progress_ratio = Decimal(self.trade_progress) / Decimal(100)
        total_days = Decimal(self.trader.duration_days)

        estimated_days = total_days * progress_ratio

        profit = Decimal(self.amount_copying) * roi_per_day * estimated_days

        return profit.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        # Automatically update profit whenever the object is saved
        self.current_profit = self.calculate_profit()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} copying {self.trader.name}"
    
class InvestmentPlan(models.Model):
    name = models.CharField(max_length=20, unique=True)

    # your existing fields
    percentage = models.DecimalField(max_digits=5, decimal_places=2)  # ROI %
    referral_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trade_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_investment = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    plan_type = models.CharField(max_length=10, default="short")  # short/long
    recurring_days = models.PositiveIntegerField(default=1)
    maximum_investment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    term = models.PositiveIntegerField(default=1)
    duration_multiplier = models.PositiveIntegerField(default=1)  # 1=day,7=week,30=month

    def __str__(self):
        return f"{self.name} - {self.percentage}%"
    
class Portfolio(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('pending', 'Pending'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='portfolios'
    )

    plan = models.ForeignKey(
        InvestmentPlan,
        on_delete=models.CASCADE,
        related_name='portfolios'
    )

    amount_invested = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_available = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    setup_date = models.DateField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    # Optional bot system
    bot_active = models.BooleanField(default=False)
    bot_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.get_name_display()} (${self.amount_invested})"
    
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('live_trade', 'Live Trade'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    STATUS_CHOICES = [
        ('win', 'Win'),
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('lost', 'Lost'),  # optional extra status
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    image = models.ImageField(upload_to='transactions', default='images/2.png')
    ref = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.type} - {self.amount} - {self.status}"
    
class PaymentMethod(models.Model):
    name = models.CharField(max_length=50)  # e.g., 'My Visa Card', 'PayPal Account'
    details = models.JSONField(blank=True, null=True)  # store card number (masked), account info, etc.
    wallet_address = models.CharField(max_length=250)
    qrcode = models.ImageField(upload_to='qrcode/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ref = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"

    def __str__(self):
        return f"{self.name}"
    
class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    ref = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_no = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_no:
            today = timezone.now().strftime("%Y%m%d")

            # Count transactions created today
            count_today = Payment.objects.filter(
                created_at__date=timezone.now().date()
            ).count() + 1

            serial = str(count_today).zfill(4)  # 0001, 0002, ...
            self.transaction_no = f"{today}{serial}"

        super().save(*args, **kwargs)

class KycVerification(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    document = models.ImageField(upload_to='kyc/')
    uploaded_on = models.DateTimeField(auto_now_add=True)
    ref = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejected_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} KYC"
    
class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('profit', 'Profit'),
    ]

    name = models.CharField(max_length=20)
    wallet_address = models.CharField(max_length=250)
    amount = models.PositiveIntegerField()
    charges = models.DecimalField(max_digits=10, decimal_places=2)
    available_for_withdraw = models.PositiveIntegerField()
    ref = models.UUIDField(default=uuid.uuid4, editable=False)
    created_on = models.DateTimeField(auto_now_add=True)
    approved_on = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    withdrawal_type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    def __str__(self):
        return f"{self.name} withdrawal"
    
class MarketCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class MarketAsset(models.Model):
    name = models.CharField(max_length=100)
    ticker = models.CharField(max_length=20, unique=True)
    image = models.ImageField(upload_to="assets/")
    percent_change_1d = models.DecimalField(max_digits=8, decimal_places=5)
    category = models.ForeignKey(MarketCategory, on_delete=models.CASCADE, related_name="assets")
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.ticker})"