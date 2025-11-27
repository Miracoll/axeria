from django.contrib import admin
from .models import User, Trader, CopyTrade, InvestmentPlan, Portfolio, Transaction, Payment, PaymentMethod, KycVerification, MarketAsset, MarketCategory, Withdrawal, Config

# Register your models here.

admin.site.register(User)
admin.site.register(Trader)
admin.site.register(CopyTrade)
admin.site.register(InvestmentPlan)
admin.site.register(Portfolio)
admin.site.register(Transaction)
admin.site.register(Payment)
admin.site.register(PaymentMethod)
admin.site.register(KycVerification)
admin.site.register(Withdrawal)
admin.site.register(MarketAsset)
admin.site.register(MarketCategory)
admin.site.register(Config)