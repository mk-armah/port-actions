import os
from github import Github
from datetime import datetime, timedelta

# Initialize GitHub client with your PAT
g = Github(os.getenv('GITHUB_TOKEN'))

# Get input variables from the environment
repo_name = os.getenv('REPOSITORY')
time_frame = int(os.getenv('TIME_FRAME'))

# Fetch the repository
repo = g.get_repo(repo_name)

# Calculate the start date for the time frame
start_date = datetime.now() - timedelta(weeks=time_frame)

def calculate_pr_metrics():
    prs = repo.get_pulls(state='all', sort='updated', direction='desc')
    
    # Initialize metric counters
    total_open_to_close_time = timedelta(0)
    total_time_to_first_review = timedelta(0)
    total_time_to_approval = timedelta(0)
    prs_opened = 0
    prs_merged = 0
    total_reviews = 0
    total_commits = 0
    total_loc_changed = 0

    for pr in prs:
        if pr.created_at < start_date:
            break  # Stop iterating once we are outside the time frame

        prs_opened += 1
        if pr.merged:
            prs_merged += 1
            total_open_to_close_time += pr.merged_at - pr.created_at
            commits = pr.get_commits()
            total_commits += commits.totalCount
            for file in pr.get_files():
                total_loc_changed += file.additions + file.deletions

            reviews = pr.get_reviews()
            for review in reviews:
                if review.state == "APPROVED":
                    total_time_to_approval += review.submitted_at - pr.created_at
                    break  # Only consider the time to the first approval

            if reviews.totalCount > 0:
                first_review = reviews[0]
                total_time_to_first_review += first_review.submitted_at - pr.created_at
                total_reviews += reviews.totalCount

    # Calculate averages
    avg_open_to_close_time = total_open_to_close_time / prs_opened if prs_opened else timedelta(0)
    avg_time_to_first_review = total_time_to_first_review / prs_opened if prs_opened else timedelta(0)
    avg_time_to_approval = total_time_to_approval / prs_opened if prs_opened else timedelta(0)
    avg_reviews_per_week = total_reviews / time_frame if time_frame else 0
    avg_commits_per_pr = total_commits / prs_opened if prs_opened else 0
    avg_loc_per_pr = total_loc_changed / prs_opened if prs_opened else 0

    # Output metrics
    print(f"Repository: {repo_name}")
    print(f"Average PR open to close time: {avg_open_to_close_time}")
    print(f"Average time to first review: {avg_time_to_first_review}")
    print(f"Average time to approval: {avg_time_to_approval}")
    print(f"PRs opened: {prs_opened}")
    print(f"Weekly PRs merged: {prs_merged / time_frame}")
    print(f"Average PRs reviewed/week: {avg_reviews_per_week}")
    print(f"Average commits per PR: {avg_commits_per_pr}")
    print(f"Avg LOC changed per PR: {avg_loc_per_pr}")

def main():
    calculate_pr_metrics()

if __name__ == "__main__":
    main()
