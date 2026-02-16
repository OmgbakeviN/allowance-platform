from django.contrib import admin
from .models import Wallet, WalletBucket, WalletTransaction

# Register your models here.
admin.site.register(Wallet)
admin.site.register(WalletBucket)
admin.site.register(WalletTransaction)