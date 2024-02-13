# import os
# from github import Github
# from datetime import datetime, timedelta, timezone
# from concurrent.futures import ThreadPoolExecutor, as_completed

# class RepositoryMetrics:
#     def __init__(self, repo_name, time_frame):
#         self.g = Github(os.getenv('GITHUB_TOKEN'))
#         self.repo_name = repo_name
#         self.time_frame = int(time_frame)
#         self.start_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(weeks=self.time_frame)
#         self.repo = self.g.get_repo(f"{self.repo_name}")

#     def calculate_pr_metrics(self):
#         prs = self.repo.get_pulls(state='all', sort='updated', direction='desc')
#         results = []

#         with ThreadPoolExecutor() as executor:
#             futures = [executor.submit(self.process_pr, pr) for pr in prs if pr.created_at >= self.start_date]
#             for future in as_completed(futures):
#                 results.append(future.result())

#         # Aggregate results
#         metrics = self.aggregate_results(results)    
        
#     def process_pr(self, pr):
#         pr_metrics = {'open_to_close_time': timedelta(0), 'time_to_first_review': timedelta(0),
#                       'time_to_approval': timedelta(0), 'prs_opened': 1, 'prs_merged': 0,
#                       'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0}

#         if pr.merged:
#             pr_metrics['prs_merged'] = 1
#             pr_metrics['open_to_close_time'] = pr.merged_at - pr.created_at
#             pr_metrics['total_commits'] = pr.get_commits().totalCount
#             pr_metrics['total_loc_changed'] = sum(file.additions + file.deletions for file in pr.get_files())

#             reviews = pr.get_reviews()
#             if reviews.totalCount > 0:
#                 first_review = reviews[0]
#                 pr_metrics['time_to_first_review'] = first_review.submitted_at - pr.created_at
#                 for review in reviews:
#                     if review.state == "APPROVED":
#                         pr_metrics['time_to_approval'] = review.submitted_at - pr.created_at
#                         break
#                 pr_metrics['total_reviews'] = reviews.totalCount

#         return pr_metrics

#     def aggregate_results(self, results):
        
#         aggregated = {'total_open_to_close_time': timedelta(0), 'total_time_to_first_review': timedelta(0),
#                       'total_time_to_approval': timedelta(0), 'prs_opened': 0, 'prs_merged': 0,
#                       'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0 }
    
#         for result in results:
#             aggregated['total_open_to_close_time'] += result['open_to_close_time']
#             aggregated['total_time_to_first_review'] += result['time_to_first_review']
#             aggregated['total_time_to_approval'] += result['time_to_approval']
#             aggregated['prs_opened'] += result['prs_opened']
#             aggregated['prs_merged'] += result['prs_merged']
#             aggregated['total_reviews'] += result['total_reviews']
#             aggregated['total_commits'] += result['total_commits']
#             aggregated['total_loc_changed'] += result['total_loc_changed']
        
#         metrics = {
#             "repository": self.repo_name,
#             "total_open_to_close_time": str(aggregated["total_open_to_close_time"]),
#             "total_time_to_first_review": str(aggregated["total_time_to_first_review"]),
#             "total_time_to_approval": str(aggregated["total_time_to_approval"]),
#             "prs_merged": aggregated["prs_merged"],
#             "total_reviews": aggregated["total_reviews"],
#             "total_commits": aggregated["total_commits"],
#             "total_loc_changed": aggregated["total_loc_changed"],
#             "average_open_to_close_time": str(
#                 aggregated["total_open_to_close_time"] / aggregated["prs_merged"]
#                 if aggregated["prs_merged"]
#                 else timedelta(0)
#             ),
#             "average_time_to_first_review": str(
#                 aggregated["total_time_to_first_review"] / aggregated["prs_opened"]
#                 if aggregated["prs_opened"]
#                 else timedelta(0)
#             ),
#             "average_time_to_approval": str(
#                 aggregated["total_time_to_approval"] / aggregated["prs_opened"]
#                 if aggregated["prs_opened"]
#                 else timedelta(0)
#             ),
#             "prs_opened": aggregated["prs_opened"],
#             "weekly_prs_merged": aggregated["prs_merged"] / self.time_frame,
            
#             "average_reviews_per_pr": (
#                 aggregated["total_reviews"] / aggregated["prs_opened"]
#                 if aggregated["prs_opened"]
#                 else 0
#             ),
#             "average_commits_per_pr": (
#                 aggregated["total_commits"] / aggregated["prs_opened"]
#                 if aggregated["prs_opened"]
#                 else 0
#             ),
#             "average_loc_changed_per_pr": (
#                 aggregated["total_loc_changed"] / aggregated["prs_opened"]
#                 if aggregated["prs_opened"]
#                 else 0
#             ),
#         }
        
#         return metrics

# def main():
#     repo_name = os.getenv('REPOSITORY')
#     time_frame = os.getenv('TIME_FRAME')
#     print("Repository Name", repo_name)
#     print("TimeFrame", time_frame)
    
#     repo_metrics = RepositoryMetrics(repo_name, time_frame)
#     metrics = repo_metrics.calculate_pr_metrics()

#     metrics_json = json.dumps(metrics)
#     print(f"::set-output name=metrics::{metrics_json}")

# if __name__ == "__main__":
#     main()



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
        self.start_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(weeks=self.time_frame)
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
            if review.state == "APPROVED":
                if pr_metrics['time_to_approval'] == timedelta(0):  # Capture time to first approval
                    pr_metrics['time_to_approval'] = review.submitted_at - pr.created_at
            if pr_metrics['time_to_first_review'] == timedelta(0):  # Capture time to first review
                pr_metrics['time_to_first_review'] = review.submitted_at - pr.created_at
            pr_metrics['total_reviews'] += 1
            pr_metrics['review_dates'].append(review.submitted_at)

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

        review_weeks = {review_date.isocalendar()[1] for review_date in aggregated['review_dates']}
        average_prs_reviewed_per_week = len(review_weeks) / self.time_frame if self.time_frame > 0 else 0

        metrics = {
            'average_open_to_close_time': aggregated['total_open_to_close_time'] / aggregated['prs_merged'] if aggregated['prs_merged'] else timedelta(0),
            'average_time_to_first_review': aggregated['total_time_to_first_review'] / aggregated['prs_opened'] if aggregated['prs_opened'] else timedelta(0),
            'average_time_to_approval': aggregated['total_time_to_approval'] / aggregated['prs_opened'] if aggregated['prs_opened'] else timedelta(0),
            'prs_opened': aggregated['prs_opened'],
            'weekly_prs_merged': aggregated['prs_merged'] / self.time_frame,
            'average_reviews_per_pr': aggregated['total_reviews'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_commits_per_pr': aggregated['total_commits'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_loc_changed_per_pr': aggregated['total_loc_changed'] / aggregated['prs_opened'] if aggregated['prs_opened'] else 0,
            'average_prs_reviewed_per_week': average_prs_reviewed_per_week
        }

        return metrics

def main():
    repo_name = os.getenv('REPOSITORY')
    time_frame = os.getenv('TIME_FRAME')
    print("Repository Name:", repo_name)
    print("TimeFrame (in weeks):", time_frame)
    
    repo_metrics = RepositoryMetrics(repo_name, time_frame)
    metrics = repo_metrics.calculate_pr_metrics()

    metrics_json = json.dumps(metrics, default=str)  # Ensure proper serialization
    print(f"::set-output name=metrics::{metrics_json}")

if __name__ == "__main__":
    main()
