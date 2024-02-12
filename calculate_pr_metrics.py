import os
import asyncio
import httpx
import json
from datetime import datetime, timedelta, timezone


class RepositoryMetrics:
    def __init__(self, repo_name, time_frame):
        self.base_url = "https://api.github.com"
        self.repo_name = repo_name
        self.time_frame = int(time_frame)
        self.start_date = datetime.now(timezone.utc) - timedelta(weeks=self.time_frame)
        self.headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github.v3+json",
        }

    # async def fetch_paginated_data(self, client, url):
    #     items = []
    #     while url:
    #         print("URL >>> ",url)
    #         response = await client.get(url)
    #         if response.status_code == 200:
    #             page_items = response.json()
    #             if page_items:
    #                 items.extend(page_items)
    #                 if "next" in response.links:
    #                     url = response.links["next"]["url"]
    #                 else:
    #                     break
    #             else:
    #                 break
    #         else:
    #             print(f"Failed to fetch data: {response.status_code}")
                
    #             break
    #     return items

    import time

    async def fetch_paginated_data(self, client, url):
        items = []
        while url:
            response = await client.get(url, headers=self.headers)
            if response.status_code == 200:
                page_items = response.json()
                items.extend(page_items)
                url = response.links.get("next", {}).get("url")
            elif response.status_code == 403 and 'Retry-After' in response.headers:
                retry_after = int(response.headers['Retry-After'])
                print(f"Rate limit exceeded for {url}. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                print(f"Failed to fetch data: {response.status_code}")
                break
        return items

    async def calculate_pr_metrics(self):
        async with httpx.AsyncClient() as client:
            prs_url = f"{self.base_url}/repos/{self.repo_name}/pulls?state=all&sort=updated&direction=desc&per_page=100"
            prs = await self.fetch_paginated_data(client, prs_url)
            prs = [
                pr
                for pr in prs
                if datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                >= self.start_date
            ]

            results = await asyncio.gather(*[self.process_pr(client, pr) for pr in prs])
            metrics = self.aggregate_results(results)
            return metrics

    async def process_pr(self, client, pr):
        pr_metrics = {
            "open_to_close_time": timedelta(0),
            "time_to_first_review": timedelta(0),
            "time_to_approval": timedelta(0),
            "prs_opened": 1,
            "prs_merged": int(pr["merged_at"] is not None),
            "reviews": 0,
            "commits": 0,
            "loc_changed": 0,
        }

        if pr["merged_at"]:
            pr_metrics["open_to_close_time"] = datetime.strptime(
                pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc) - datetime.strptime(
                pr["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(
                tzinfo=timezone.utc
            )
            commits_url = pr["commits_url"]
            commits = await self.fetch_paginated_data(client, commits_url)
            pr_metrics["commits"] = len(commits)

            files_url = pr["_links"]["self"]["href"] + "/files"
            files = await self.fetch_paginated_data(client, files_url)
            pr_metrics["loc_changed"] = sum(
                file["additions"] + file["deletions"] for file in files
            )

            reviews_url = pr["_links"]["self"]["href"] + "/reviews"
            reviews = await self.fetch_paginated_data(client, reviews_url)
            pr_metrics["reviews"] = len(reviews)
            if reviews:
                first_review = reviews[0]
                pr_metrics["time_to_first_review"] = datetime.strptime(
                    first_review["submitted_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc) - datetime.strptime(
                    pr["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(
                    tzinfo=timezone.utc
                )
                for review in reviews:
                    if review["state"] == "APPROVED":
                        pr_metrics["time_to_approval"] = datetime.strptime(
                            review["submitted_at"], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=timezone.utc) - datetime.strptime(
                            pr["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(
                            tzinfo=timezone.utc
                        )
                        break

        return pr_metrics

    def aggregate_results(self, results):
        aggregated = {
            "total_open_to_close_time": timedelta(0),
            "total_time_to_first_review": timedelta(0),
            "total_time_to_approval": timedelta(0),
            "prs_opened": 0,
            "prs_merged": 0,
            "total_reviews": 0,
            "total_commits": 0,
            "total_loc_changed": 0,
        }
        for result in results:
            aggregated["total_open_to_close_time"] += result["open_to_close_time"]
            aggregated["total_time_to_first_review"] += result["time_to_first_review"]
            aggregated["total_time_to_approval"] += result["time_to_approval"]
            aggregated["prs_opened"] += result["prs_opened"]
            aggregated["prs_merged"] += result["prs_merged"]
            aggregated["total_reviews"] += result["reviews"]
            aggregated["total_commits"] += result["commits"]
            aggregated["total_loc_changed"] += result["loc_changed"]

        metrics = {
            "repository": self.repo_name,
            "total_open_to_close_time": str(aggregated["total_open_to_close_time"]),
            "total_time_to_first_review": str(aggregated["total_time_to_first_review"]),
            "total_time_to_approval": str(aggregated["total_time_to_approval"]),
            "prs_merged": aggregated["prs_merged"],
            "total_reviews": aggregated["total_reviews"],
            "total_commits": aggregated["total_commits"],
            "total_loc_changed": aggregated["total_loc_changed"],
            "average_open_to_close_time": str(
                aggregated["total_open_to_close_time"] / aggregated["prs_merged"]
                if aggregated["prs_merged"]
                else timedelta(0)
            ),
            "average_time_to_first_review": str(
                aggregated["total_time_to_first_review"] / aggregated["prs_opened"]
                if aggregated["prs_opened"]
                else timedelta(0)
            ),
            "average_time_to_approval": str(
                aggregated["total_time_to_approval"] / aggregated["prs_opened"]
                if aggregated["prs_opened"]
                else timedelta(0)
            ),
            "prs_opened": aggregated["prs_opened"],
            "weekly_prs_merged": aggregated["prs_merged"] / self.time_frame,
            "average_reviews_per_pr": (
                aggregated["total_reviews"] / aggregated["prs_opened"]
                if aggregated["prs_opened"]
                else 0
            ),
            "average_commits_per_pr": (
                aggregated["total_commits"] / aggregated["prs_opened"]
                if aggregated["prs_opened"]
                else 0
            ),
            "average_loc_changed_per_pr": (
                aggregated["total_loc_changed"] / aggregated["prs_opened"]
                if aggregated["prs_opened"]
                else 0
            ),
        }

        return metrics


async def main():
    repo_name = os.getenv("REPOSITORY")
    time_frame = os.getenv("TIME_FRAME")
    print("Repository Name", repo_name)
    print("TimeFrame", time_frame)

    repo_metrics = RepositoryMetrics(repo_name, time_frame)
    metrics = await repo_metrics.calculate_pr_metrics()
    metrics_json = json.dumps(metrics)
    print(f"::set-output name=metrics::{metrics_json}")


if __name__ == "__main__":
    asyncio.run(main())
