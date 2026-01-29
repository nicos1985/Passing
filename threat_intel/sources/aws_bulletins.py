# threat_intel/sources/aws_bulletins.py
import feedparser
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

AWS_BULLETINS_FEED = "https://aws.amazon.com/security/security-bulletins/feed"

class AwsBulletinsConnector:
    code = "AWS"

    def fetch(self, start_dt, end_dt, cursor=None):
        feed = feedparser.parse(AWS_BULLETINS_FEED)

        items = []
        for e in feed.entries:
            published = None

            parsed = (
                getattr(e, "published_parsed", None)
                or getattr(e, "updated_parsed", None)
            )

            if parsed:
                dt = datetime(*parsed[:6])  # naive
                published = timezone.make_aware(dt, dt_timezone.utc)

            url = getattr(e, "link", None)
            title = getattr(e, "title", "AWS Security Bulletin")
            external_id = url or title

            if published:
                if published < start_dt or published > end_dt:
                    continue

            items.append({
                "external_id": external_id,
                "published_at": published,
                "url": url,
                "title": title,
                "payload": {"summary": getattr(e, "summary", "")},
            })

        new_cursor = {"last_run_end": end_dt.isoformat()}
        return items, new_cursor
