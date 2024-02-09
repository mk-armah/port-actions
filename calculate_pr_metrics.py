import os
import asyncio
import httpx
from datetime import datetime, timedelta, timezone

class RepositoryMetrics:
    def __init__(self, repo_name, time_frame):
        self.base_url = "https://api.github.com"
        self.repo_name = repo_name
        self.time_frame = int(time_frame)
        self.start_date = datetime.now(timezone.utc) - timedelta(weeks=self.time_frame)
        self.headers = {
            "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github.v3+json"
        }

    async def fetch_paginated_data(self, client, url):
        items = []
        while url:
            response = await client.get(url, headers=self.headers)
            page_items = response.json()
            if page_items:
                items.extend(page_items)
                if 'next' in response.links:
                    url = response.links['next']['url']
                else:
                    break
            else:
                break
        return items

    async def calculate_pr_metrics(self):
        async with httpx.AsyncClient() as client:
            prs_url = f"{self.base_url}/repos/port-labs/{self.repo_name}/pulls?state=all&sort=updated&direction=desc&per_page=100"
            prs = await self.fetch_paginated_data(client, prs_url)
            prs = [pr for pr in prs if datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) >= self.start_date]

            results = await asyncio.gather(*[self.process_pr(client, pr) for pr in prs])
            metrics = self.aggregate_results(results)
            self.print_metrics(metrics)

    async def process_pr(self, client, pr):
        pr_metrics = {'open_to_close_time': timedelta(0), 'time_to_first_review': timedelta(0),
                      'time_to_approval': timedelta(0), 'prs_opened': 1, 'prs_merged': 0,
                      'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0}

        pr_metrics['prs_opened'] = 1
        merged_at = pr.get('merged_at')
        if merged_at:
            pr_metrics['prs_merged'] = 1
            pr_metrics['open_to_close_time'] = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

            commits_url = pr['commits_url']
            commits = await self.fetch_paginated_data(client, commits_url)
            pr_metrics['total_commits'] = len(commits)

            files_url = pr['_links']['self']['href'] + '/files'
            files = await self.fetch_paginated_data(client, files_url)
            pr_metrics['total_loc_changed'] = sum(file['additions'] + file['deletions'] for file in files)

            reviews_url = pr['_links']['self']['href'] + '/reviews'
            reviews = await self.fetch_paginated_data(client, reviews_url)
            if reviews:
                pr_metrics['total_reviews'] = len(reviews)
                first_review = reviews[0]
                pr_metrics['time_to_first_review'] = datetime.strptime(first_review['submitted_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                for review in reviews:
                    if review['state'] == "APPROVED":
                        pr_metrics['time_to_approval'] = datetime.strptime(review['submitted_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        break

        return pr_metrics

    def aggregate_results(self, results):
        aggregated = {'total_open_to_close_time': timedelta(0), 'total_time_to_first_review': timedelta(0),
                      'total_time_to_approval': timedelta(0), 'prs_opened': 0, 'prs_merged': 0,
                      'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0}
        for result in results:
            for key in aggregated:
                aggregated[key] += result[key]
        return aggregated

    def print_metrics(self, metrics):
        avg_open_to_close_time = metrics['total_open_to_close_time'] / metrics['prs_opened'] if metrics['prs_opened'] else timedelta(0)
        avg_time_to_first_review = metrics['total_time_to_first_review'] / metrics['prs_opened'] if metrics['prs_opened'] else timedelta(0)
        avg_time_to_approval = metrics['total_time_to_approval'] / metrics['prs_opened'] if metrics['prs_opened'] else timedelta(0)
        avg_reviews_per_week = metrics['total_reviews'] / self.time_frame if self.time_frame else 0
        avg_commits_per_pr = metrics['total_commits'] / metrics['prs_opened'] if metrics['prs_opened'] else 0
        avg_loc_per_pr = metrics['total_loc_changed'] / metrics['prs_opened'] if metrics['prs_opened'] else 0

        print(f"Repository: {self.repo_name}")
        print(f"Average PR open to close time: {avg_open_to_close_time}")
        print(f"Average time to first review: {avg_time_to_first_review}")
        print(f"Average time to approval: {avg_time_to_approval}")
        print(f"PRs opened: {metrics['prs_opened']}")
        print(f"Weekly PRs merged: {metrics['prs_merged'] / self.time_frame}")
        print(f"Average PRs reviewed/week: {avg_reviews_per_week}")
        print(f"Average commits per PR: {avg_commits_per_pr}")
        print(f"Avg LOC changed per PR: {avg_loc_per_pr}")

async def main():
    repo_name = os.getenv('REPOSITORY')
    time_frame = os.getenv('TIME_FRAME')
    print("Repository Name", repo_name)
    print("TimeFrame", time_frame)

    metrics = RepositoryMetrics(repo_name, time_frame)
    await metrics.calculate_pr_metrics()

if __name__ == "__main__":
    asyncio.run(main())
