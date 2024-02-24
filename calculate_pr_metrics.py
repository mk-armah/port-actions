import os
from github import Github
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

class RepositoryMetrics:
    def __init__(self, repo_name, time_frame):
        self.g = Github(os.getenv('GITHUB_TOKEN'))
        self.repo_name = repo_name
        self.time_frame = int(time_frame)
        self.start_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=self.time_frame)
        self.repo = self.g.get_repo(f"{self.repo_name}")

    def calculate_pr_metrics(self):
        prs = self.repo.get_pulls(state='all', sort='created', direction='desc')
        results = []

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.process_pr, pr) for pr in prs if pr.created_at >= self.start_date]
            for future in as_completed(futures):
                results.append(future.result())

        metrics = self.aggregate_results(results)
        return metrics

    def process_pr(self, pr):
        pr_metrics = {
            'open_to_close_time': timedelta(0),
            'time_to_first_review': timedelta(0),
            'time_to_approval': timedelta(0),
            'prs_opened': 1,
            'prs_merged': int(pr.merged),
            'total_reviews': 0,
            'total_commits': 0,
            'total_loc_changed': 0,
            'review_dates': []
        }

        if pr.merged:
            pr_metrics['open_to_close_time'] = pr.merged_at - pr.created_at
            commits = pr.get_commits()
            pr_metrics['total_commits'] = commits.totalCount
            for file in pr.get_files():
                pr_metrics['total_loc_changed'] += file.additions + file.deletions

        reviews = pr.get_reviews()
        for review in reviews:
            if review.state in ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"]:
                pr_metrics['review_dates'].append(review.submitted_at)
                pr_metrics['total_reviews'] += 1
                if pr_metrics['time_to_first_review'] == timedelta(0):
                    pr_metrics['time_to_first_review'] = review.submitted_at - pr.created_at
                if review.state == "APPROVED" and pr_metrics['time_to_approval'] == timedelta(0):
                    pr_metrics['time_to_approval'] = review.submitted_at - pr.created_at

        return pr_metrics

    def aggregate_results(self, results):
        aggregated = {
            'total_open_to_close_time': timedelta(0),
            'total_time_to_first_review': timedelta(0),
            'total_time_to_approval': timedelta(0),
            'prs_opened': 0,
            'prs_merged': 0,
            'total_reviews': 0,
            'total_commits': 0,
            'total_loc_changed': 0,
            'review_dates': []
        }

        for result in results:
            aggregated['total_open_to_close_time'] += result['open_to_close_time']
            aggregated['total_time_to_first_review'] += result['time_to_first_review']
            aggregated['total_time_to_approval'] += result['time_to_approval']
            aggregated['prs_opened'] += result['prs_opened']
            aggregated['prs_merged'] += result['prs_merged']
            aggregated['total_reviews'] += result['total_reviews']
            aggregated['total_commits'] += result['total_commits']
            aggregated['total_loc_changed'] += result['total_loc_changed']
            aggregated['review_dates'].extend(result['review_dates'])

        # Calculate average PRs reviewed per week
        review_weeks = {review_date.isocalendar()[1] for review_date in aggregated['review_dates']}
        average_prs_reviewed_per_week = len(review_weeks) / max(1, self.time_frame)

        metrics = {
            "id": self.repo.id,
            'average_open_to_close_time': self.timedelta_to_decimal_hours(aggregated['total_open_to_close_time'] / aggregated['prs_merged']) if aggregated['prs_merged'] else 0,
            'average_time_to_first_review': self.timedelta_to_decimal_hours(aggregated['total_time_to_first_review'] / aggregated['prs_opened']) if aggregated['prs_opened'] else 0,
            'average_time_to_approval': self.timedelta_to_decimal_hours(aggregated['total_time_to_approval'] / aggregated['prs_opened']) if aggregated['prs_opened'] else 0,
            'prs_opened': aggregated['prs_opened'],
            'weekly_prs_merged': self.timedelta_to_decimal_hours(aggregated['total_open_to_close_time'] / max(1, self.time_frame)) if aggregated['prs_merged'] else 0,
            'average_reviews_per_pr': aggregated['total_reviews'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_commits_per_pr': aggregated['total_commits'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_loc_changed_per_pr': aggregated['total_loc_changed'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_prs_reviewed_per_week': average_prs_reviewed_per_week
        }

        return metrics

    def timedelta_to_decimal_hours(self, td):
        return round(td.total_seconds() / 3600, 2)

def main():
    repo_name = os.getenv('REPOSITORY')
    time_frame = os.getenv('TIME_FRAME_IN_DAYS') #os.getenv('TIME_FRAME')
    print("Repository Name:", repo_name)
    print("TimeFrame (in weeks):", time_frame)
    
    repo_metrics = RepositoryMetrics(repo_name, time_frame)
    metrics = repo_metrics.calculate_pr_metrics()

    metrics_json = json.dumps(metrics, default=str)  # Ensure proper serialization
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"metrics={metrics_json}\n")

if __name__ == "__main__":
    main()
