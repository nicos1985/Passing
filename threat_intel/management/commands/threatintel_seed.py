from django.core.management.base import BaseCommand
from threat_intel.models import Source, TechTag

class Command(BaseCommand):
    help = "Seed initial Threat Intel sources and TechTags"

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-fortinet",
            action="store_true",
            help="Also seed Fortinet PSIRT source and tags",
        )
        parser.add_argument(
            "--reset-keywords",
            action="store_true",
            help="Overwrite TechTag.keywords even if tag exists",
        )

    def handle(self, *args, **opts):
        with_fortinet = opts["with_fortinet"]
        reset_keywords = opts["reset_keywords"]

        # 1) Sources
        sources = [
            {
                "code": "NVD",
                "name": "NIST NVD (CVE API)",
                "kind": "api",
                "base_url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
            },
            {
                "code": "AWS",
                "name": "AWS Security Bulletins (RSS)",
                "kind": "rss",
                "base_url": "https://aws.amazon.com/security/security-bulletins/",
            },
        ]

        if with_fortinet:
            sources.append(
                {
                    "code": "FORTINET",
                    "name": "Fortinet PSIRT Advisories",
                    "kind": "rss",
                    "base_url": "https://www.fortiguard.com/psirt",
                }
            )

        created_s = 0
        updated_s = 0

        for s in sources:
            obj, created = Source.objects.update_or_create(
                code=s["code"],
                defaults={
                    "name": s["name"],
                    "kind": s["kind"],
                    "base_url": s["base_url"],
                    "is_active": True,
                },
            )
            if created:
                created_s += 1
            else:
                updated_s += 1

        # 2) TechTags (stack “must watch”)
        tags = [
            {
                "name": "Ubuntu Linux",
                "keywords": [
                    "ubuntu", "canonical", "jammy", "focal", "bionic", "openssl", "glibc", "sudo"
                ],
            },
            {
                "name": "MySQL",
                "keywords": [
                    "mysql", "mysqld", "innodb", "percona"
                ],
            },
            {
                "name": "Laravel",
                "keywords": [
                    "laravel", "illuminate", "symfony", "composer"
                ],
            },
            {
                "name": "React / Node / npm",
                "keywords": [
                    "node", "nodejs", "npm", "yarn",
                    "package.json", "webpack", "vite", "next.js"
                ],
            },
            {
                "name": "AWS / EC2",
                "keywords": ["ec2","iam","vpc","security group","ssm","alb","cloudwatch","rds"],
            },
            {
                "name": "Cloudflare WAF",
                "keywords":["cloudflare","waf","ruleset","managed rules"],
            },
        ]

        if with_fortinet:
            tags.append(
                {
                    "name": "Fortinet",
                    "keywords": [
                        "fortinet", "fortigate", "fortios", "fortiguard",
                        "fortiproxy", "fortimanager", "fortianalyzer"
                    ],
                }
            )

        created_t = 0
        updated_t = 0

        for t in tags:
            obj, created = TechTag.objects.get_or_create(name=t["name"])
            if created:
                obj.keywords = t["keywords"]
                obj.is_active = True
                obj.save()
                created_t += 1
            else:
                changed = False
                if reset_keywords:
                    obj.keywords = t["keywords"]
                    changed = True
                if not obj.is_active:
                    obj.is_active = True
                    changed = True
                if changed:
                    obj.save()
                    updated_t += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Sources: created={created_s}, updated={updated_s}. "
            f"TechTags: created={created_t}, updated={updated_t}."
        ))

        self.stdout.write("Next steps:")
        self.stdout.write("- Run: python manage.py threatintel_run --days 30 --dry-run")
        self.stdout.write("- Then: python manage.py threatintel_run --days 30 --send-email")
