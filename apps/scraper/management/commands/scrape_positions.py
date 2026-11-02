"""Django management command — entry point for `python manage.py scrape_positions`."""
from __future__ import annotations

import asyncio
import logging

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError

from ...orchestrator.scraper import PositionScraper
from ...pipeline.django_pipeline import DjangoPositionPipeline
from ...services.site_config_provider import website_to_config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape positions for a website (by id or name)"

    def add_arguments(self, parser):
        parser.add_argument("--website", type=str, required=True,
                            help="Website id or name")
        parser.add_argument("--max-pages", type=int, default=None,
                            help="Override max_pages from config")
        parser.add_argument("--debug", action="store_true",
                            help="Enable DEBUG logging")
        parser.add_argument("--no-browser", action="store_true",
                            help="Disable browser fallback (HTTP only)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Don't save to DB; print extracted items only")

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.DEBUG if options["debug"] else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        website = self._get_website(options["website"])

        config = website_to_config(website)
        if options["max_pages"]:
            config.max_pages = options["max_pages"]
        if options["no_browser"]:
            config.use_browser_fallback = False

        pipeline = None if options["dry_run"] else DjangoPositionPipeline(website)
        scraper = PositionScraper(config=config, pipeline=pipeline)

        try:
            stats = asyncio.run(self._run(scraper, pipeline))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted"))
            return
        except Exception as e:
            logger.exception("Scrape failed")
            raise CommandError(str(e))

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY RUN] Processed {stats.saved + stats.skipped} positions"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Saved={stats.saved}  Skipped={stats.skipped}  "
                f"Failed={stats.failed}  Pages={stats.pages}  "
                f"Elapsed={stats.elapsed_s:.1f}s"
            ))

    async def _run(self, scraper, pipeline):
        if pipeline is None:
            # Dry-run mode: just iterate, count, and print
            saved = skipped = failed = 0
            async for item in scraper.iter_positions():
                try:
                    self.stdout.write(f"  → {item.title[:80]}  ({item.url})")
                    saved += 1
                except Exception:
                    failed += 1
            await scraper.fetcher.close()
            from ...domain.models import ScrapeStats
            return ScrapeStats(saved=saved, skipped=skipped, failed=failed, pages=1)

        await pipeline.warmup()
        try:
            return await scraper.run()
        finally:
            await pipeline.close()

    def _get_website(self, ident: str):
        from apps.websites.models import Website
        try:
            if ident.isdigit():
                return Website.objects.get(pk=int(ident))
            return Website.objects.get(name=ident)
        except Website.DoesNotExist:
            raise CommandError(f"Website '{ident}' not found")
