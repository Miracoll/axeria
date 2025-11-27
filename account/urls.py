from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('fund/', views.fund, name='fund'),
    path('invoice/<uuid:ref>/', views.invoice, name='invoice'),
    path('invest/', views.invest, name='invest'),
    path('withdrawal/', views.choose_withdrawal, name='withdraw'),
    path('balance-withdrawal/', views.balance_withdrawal, name='balance-withdraw'),
    path('profit-withdrawal/', views.profit_withdrawal, name='profit-withdraw'),
    path('assets/', views.assets, name='assets'),
    path('stocks/', views.stock, name='stocks'),
    path('trades/', views.trades, name='trades'),
    path('traders/copy/', views.copy_trader, name='copy-trader'),
    path('chart/', views.chart, name='chart'),
    path('transaction/', views.transactions, name='transactions'),
    path('create-portfolio', views.create_portfolio, name='create-portfolio'),
    path('plan/<str:amount>/', views.plan, name='plan'),
    path('kyc/', views.kyc, name='kyc'),
    path('profile/', views.profile, name='profile')
]