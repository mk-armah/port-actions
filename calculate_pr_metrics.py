stable

# import os
# from github import Github
# from datetime import datetime, timedelta,timezone

# # Initialize GitHub client with your PAT
# g = Github(os.getenv('GITHUB_TOKEN'))

# # Get input variables from the environment
# repo_name = os.getenv('REPOSITORY')
# time_frame = int(os.getenv('TIME_FRAME'))

# # Fetch the repository
# print("Repository Name", repo_name)
# print("TimeFrame",time_frame)

# repo = g.get_repo(f"port-labs/{repo_name}")

# # Calculate the start date for the time frame
# start_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(weeks=time_frame)

# def calculate_pr_metrics():
#     prs = repo.get_pulls(state='all', sort='updated', direction='desc')
    
#     # Initialize metric counters
#     total_open_to_close_time = timedelta(0)
#     total_time_to_first_review = timedelta(0)
#     total_time_to_approval = timedelta(0)
#     prs_opened = 0
#     prs_merged = 0
#     total_reviews = 0
#     total_commits = 0
#     total_loc_changed = 0

#     for pr in prs:
#         if pr.created_at < start_date:
#             break  # Stop iterating once we are outside the time frame

#         prs_opened += 1
#         if pr.merged:
#             prs_merged += 1
#             total_open_to_close_time += pr.merged_at - pr.created_at
#             commits = pr.get_commits()
#             total_commits += commits.totalCount
#             for file in pr.get_files():
#                 total_loc_changed += file.additions + file.deletions

#             reviews = pr.get_reviews()
#             for review in reviews:
#                 if review.state == "APPROVED":
#                     total_time_to_approval += review.submitted_at - pr.created_at
#                     break  # Only consider the time to the first approval

#             if reviews.totalCount > 0:
#                 first_review = reviews[0]
#                 total_time_to_first_review += first_review.submitted_at - pr.created_at
#                 total_reviews += reviews.totalCount

#     # Calculate averages
#     avg_open_to_close_time = total_open_to_close_time / prs_opened if prs_opened else timedelta(0)
#     avg_time_to_first_review = total_time_to_first_review / prs_opened if prs_opened else timedelta(0)
#     avg_time_to_approval = total_time_to_approval / prs_opened if prs_opened else timedelta(0)
#     avg_reviews_per_week = total_reviews / time_frame if time_frame else 0
#     avg_commits_per_pr = total_commits / prs_opened if prs_opened else 0
#     avg_loc_per_pr = total_loc_changed / prs_opened if prs_opened else 0

#     # Output metrics
#     print(f"Repository: {repo_name}")
#     print(f"Average PR open to close time: {avg_open_to_close_time}")
#     print(f"Average time to first review: {avg_time_to_first_review}")
#     print(f"Average time to approval: {avg_time_to_approval}")
#     print(f"PRs opened: {prs_opened}")
#     print(f"Weekly PRs merged: {prs_merged / time_frame}")
#     print(f"Average PRs reviewed/week: {avg_reviews_per_week}")
#     print(f"Average commits per PR: {avg_commits_per_pr}")
#     print(f"Avg LOC changed per PR: {avg_loc_per_pr}")

# def main():
#     calculate_pr_metrics()

# if __name__ == "__main__":
#     main()



import os
from github import Github
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

class RepositoryMetrics:
    def __init__(self, repo_name, time_frame):
        self.g = Github(os.getenv('GITHUB_TOKEN'))
        self.repo_name = repo_name
        self.time_frame = int(time_frame)
        self.start_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(weeks=self.time_frame)
        self.repo = self.g.get_repo(f"port-labs/{self.repo_name}")

    def calculate_pr_metrics(self):
        prs = self.repo.get_pulls(state='all', sort='updated', direction='desc')
        results = []

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.process_pr, pr) for pr in prs if pr.created_at >= self.start_date]
            for future in as_completed(futures):
                results.append(future.result())

        # Aggregate results
        metrics = self.aggregate_results(results)

        # Output metrics
        self.print_metrics(metrics)

    def process_pr(self, pr):
        pr_metrics = {'open_to_close_time': timedelta(0), 'time_to_first_review': timedelta(0),
                      'time_to_approval': timedelta(0), 'prs_opened': 1, 'prs_merged': 0,
                      'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0}

        if pr.merged:
            pr_metrics['prs_merged'] = 1
            pr_metrics['open_to_close_time'] = pr.merged_at - pr.created_at
            pr_metrics['total_commits'] = pr.get_commits().totalCount
            pr_metrics['total_loc_changed'] = sum(file.additions + file.deletions for file in pr.get_files())

            reviews = pr.get_reviews()
            if reviews.totalCount > 0:
                first_review = reviews[0]
                pr_metrics['time_to_first_review'] = first_review.submitted_at - pr.created_at
                for review in reviews:
                    if review.state == "APPROVED":
                        pr_metrics['time_to_approval'] = review.submitted_at - pr.created_at
                        break
                pr_metrics['total_reviews'] = reviews.totalCount

        return pr_metrics

    def aggregate_results(self, results):
        aggregated = {'total_open_to_close_time': timedelta(0), 'total_time_to_first_review': timedelta(0),
                      'total_time_to_approval': timedelta(0), 'prs_opened': 0, 'prs_merged': 0,
                      'total_reviews': 0, 'total_commits': 0, 'total_loc_changed': 0}
    
        for result in results:
            aggregated['total_open_to_close_time'] += result['open_to_close_time']
            aggregated['total_time_to_first_review'] += result['time_to_first_review']
            aggregated['total_time_to_approval'] += result['time_to_approval']
            aggregated['prs_opened'] += result['prs_opened']
            aggregated['prs_merged'] += result['prs_merged']
            aggregated['total_reviews'] += result['total_reviews']
            aggregated['total_commits'] += result['total_commits']
            aggregated['total_loc_changed'] += result['total_loc_changed']
    
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

def main():
    repo_name = os.getenv('REPOSITORY')
    time_frame = os.getenv('TIME_FRAME')
    print("Repository Name", repo_name)
    print("TimeFrame", time_frame)
    
    metrics = RepositoryMetrics(repo_name, time_frame)
    metrics.calculate_pr_metrics()

if __name__ == "__main__":
    main()
