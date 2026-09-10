from django.core.management.base import BaseCommand, CommandError

from er_tasks.sync import SyncAlreadyRunning, SyncConfigError, run_sync


class Command(BaseCommand):
    help = "Pull Eva tasks into the database (same work as POST /er/api/sync/)."

    def handle(self, *args, **options):
        try:
            result = run_sync()
        except SyncAlreadyRunning as exc:
            raise CommandError(str(exc)) from exc
        except SyncConfigError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"ok tasks={result['tasks_upserted']} watermark={result['watermark']} "
            f"in {result['duration_sec']}s"
        )
