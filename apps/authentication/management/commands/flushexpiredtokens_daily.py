from django.core.management.base import BaseCommand
from rest_framework_simplejwt.token_blacklist.management.commands.flushexpiredtokens import (
    Command as BaseFlushExpiredTokensCommand,
)


class Command(BaseCommand):
    help = "Flushes expired tokens daily"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Running flushexpiredtokens daily task..."))
        BaseFlushExpiredTokensCommand().handle(*args, **options)  # Execute the original command
        self.stdout.write(self.style.SUCCESS("flushexpiredtokens daily task completed."))
