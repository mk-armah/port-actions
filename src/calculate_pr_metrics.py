import os
from github import Github
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RepositoryMetrics:
    def __init__(self, owner, repo, timeframe,pat_token):
        self.github_client = Github(pat_token)
        self.repo_name = f"{owner}/{repo}"
        self.timeframe = int(timeframe)
        self.start_date = datetime.datetime.now(datetime.UTC).replace(
            tzinfo=datetime.timezone.utc
        ) - datetime.timedelta(days=self.timeframe)
        self.repo = self.github_client.get_repo(f"{self.repo_name}")

    def calculate_pr_metrics(self):
        prs = self.repo.get_pulls(state="all", sort="created", direction="desc")
        results = []

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.process_pr, pr)
                for pr in prs
                if pr.created_at >= self.start_date
            ]
            for future in as_completed(futures):
                results.append(future.result())

        metrics = self.aggregate_results(results)
        return metrics

    def process_pr(self, pr):
        pr_metrics = {
            "open_to_close_time": datetime.timedelta(0),
            "time_to_first_review": datetime.timedelta(0),
            "time_to_approval": datetime.timedelta(0),
            "prs_opened": 1,
            "prs_merged": int(pr.merged),
            "total_reviews": 0,
            "total_commits": 0,
            "total_loc_changed": 0,
            "review_dates": [],
        }

        if pr.merged:
            pr_metrics["open_to_close_time"] = pr.merged_at - pr.created_at
            commits = pr.get_commits()
            pr_metrics["total_commits"] = commits.totalCount
            for file in pr.get_files():
                pr_metrics["total_loc_changed"] += file.additions + file.deletions

        reviews = pr.get_reviews()
        for review in reviews:
            if review.state in ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"]:
                pr_metrics["review_dates"].append(review.submitted_at)
                pr_metrics["total_reviews"] += 1
                if pr_metrics["time_to_first_review"] == datetime.timedelta(0):
                    pr_metrics["time_to_first_review"] = (
                        review.submitted_at - pr.created_at
                    )
                if review.state == "APPROVED" and pr_metrics[
                    "time_to_approval"
                ] == datetime.timedelta(0):
                    pr_metrics["time_to_approval"] = review.submitted_at - pr.created_at

        return pr_metrics
        
    def calculate_response_rate(self, prs, team_name):
        total_requests = 0
        responded_requests = 0

        for pr in prs:
            if pr.created_at >= self.start_date:
                total_requests += 1
                if pr.get_reviews().totalCount > 0:
                    responded_requests += 1

        response_rate = (responded_requests / total_requests) * 100 if total_requests else 0

        return {f"{team_name}_response_rate": round(response_rate, 2)}

    def calculate_response_time(self, prs, team_name):
        total_response_time = datetime.timedelta(0)
        total_responses = 0

        for pr in prs:
            if pr.created_at >= self.start_date:
                reviews = pr.get_reviews()
                for review in reviews:
                    if review.user.login == team_name:
                        response_time = review.submitted_at - pr.created_at
                        total_response_time += response_time
                        total_responses += 1
                        break

        average_response_time = self.timedelta_to_decimal_hours(
            total_response_time / total_responses
        ) if total_responses else 0

        return {f"{team_name}_average_response_time": average_response_time}
        
    def aggregate_results(self, results):
            aggregated = {
                "total_open_to_close_time": datetime.timedelta(0),
                "total_time_to_first_review": datetime.timedelta(0),
                "total_time_to_approval": datetime.timedelta(0),
                "prs_opened": 0,
                "prs_merged": 0,
                "total_reviews": 0,
                "total_commits": 0,
                "total_loc_changed": 0,
                "review_dates": [],
            }
    
            for result in results:
                aggregated["total_open_to_close_time"] += result["open_to_close_time"]
                aggregated["total_time_to_first_review"] += result["time_to_first_review"]
                aggregated["total_time_to_approval"] += result["time_to_approval"]
                aggregated["prs_opened"] += result["prs_opened"]
                aggregated["prs_merged"] += result["prs_merged"]
                aggregated["total_reviews"] += result["total_reviews"]
                aggregated["total_commits"] += result["total_commits"]
                aggregated["total_loc_changed"] += result["total_loc_changed"]
                aggregated["review_dates"].extend(result["review_dates"])
    
            # Calculate average PRs reviewed per week
            review_weeks = {
                review_date.isocalendar()[1] for review_date in aggregated["review_dates"]
            }
            average_prs_reviewed_per_week = len(review_weeks) / max(1, self.timeframe / 7)
    
            metrics = {
                "id": self.repo.id,
                "average_open_to_close_time": self.timedelta_to_decimal_hours(
                    aggregated["total_open_to_close_time"] / aggregated["prs_merged"]
                )
                if aggregated["prs_merged"]
                else 0,
                "average_time_to_first_review": self.timedelta_to_decimal_hours(
                    aggregated["total_time_to_first_review"] / aggregated["prs_opened"]
                )
                if aggregated["prs_opened"]
                else 0,
                "average_time_to_approval": self.timedelta_to_decimal_hours(
                    aggregated["total_time_to_approval"] / aggregated["prs_opened"]
                )
                if aggregated["prs_opened"]
                else 0,
                "prs_opened": aggregated["prs_opened"],
                "weekly_prs_merged": self.timedelta_to_decimal_hours(
                    aggregated["total_open_to_close_time"] / max(1, self.timeframe / 7)
                )
                if aggregated["prs_merged"]
                else 0,
                "average_reviews_per_pr": round(
                    aggregated["total_reviews"] / aggregated["prs_opened"], 2
                )
                if aggregated["prs_opened"]
                else 0,
                "average_commits_per_pr": round(
                    aggregated["total_commits"] / aggregated["prs_opened"], 2
                )
                if aggregated["prs_opened"]
                else 0,
                "average_loc_changed_per_pr": round(
                    aggregated["total_loc_changed"] / aggregated["prs_opened"], 2
                )
                if aggregated["prs_opened"]
                else 0,
                "average_prs_reviewed_per_week": round(average_prs_reviewed_per_week, 2),
            }
            return metrics

    def timedelta_to_decimal_hours(self, td):
        return round(td.total_seconds() / 3600, 2)

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Calculate Pull Request Metrics.')
    parser.add_argument('--owner', required=True, help='Owner of the repository')
    parser.add_argument('--repo', required=True, help='Repository name')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--timeframe', type=int, default=30, help='Timeframe in days')
    parser.add_argument('--platform', default='github-actions', choices=['github-actions', 'self-hosted'], help='CI/CD platform type')
    args = parser.parse_args()

    logging.info(f"Repository Name: {args.owner}/{args.repo}")
    logging.info(f"TimeFrame (in days): {args.timeframe}")

    repo_metrics = RepositoryMetrics(args.owner, args.repo, args.timeframe, pat_token=args.token)
    metrics = repo_metrics.calculate_pr_metrics()
    metrics_json = json.dumps(metrics, default=str)

    if args.platform == "github-actions":
        with open(os.getenv("GITHUB_ENV"), "a") as github_env:
            github_env.write(f"metrics={metrics_json}\n")
