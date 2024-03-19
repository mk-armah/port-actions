from github import Github
import datetime
import os
import json

class GitHubAnalytics:
    def __init__(self, owner_repo, workflows, branch, number_of_days, commit_counting_method, token=None):
        self.owner, self.repo_name = owner_repo.split('/')
        self.workflows = workflows.split(',')  # Assuming workflows is a comma-separated string
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method
        self.github = Github(token) if token else Github()
        self.repo = self.github.get_repo(f"{self.owner}/{self.repo_name}")

    def calculate_lead_times(self):
        pr_lead_times = self._calculate_pr_lead_times()
        workflow_lead_times = self._calculate_workflow_lead_times()

        average_pr_time = sum(pr_lead_times) / len(pr_lead_times) if pr_lead_times else 0
        average_workflow_time = sum(workflow_lead_times) / len(workflow_lead_times) if workflow_lead_times else 0

        lead_time_for_changes = average_pr_time + average_workflow_time
        rating, color = self._determine_rating(lead_time_for_changes)

        return {
            "PRAverageTimeDuration": round(average_pr_time, 2),
            "WorkflowAverageTimeDuration": round(average_workflow_time, 2),
            "LeadTimeForChangesInHours": lead_time_for_changes,
            "Rating": rating,
            "Color": color
        }

    def _calculate_pr_lead_times(self):
        start_date = datetime.datetime.now() - datetime.timedelta(days=self.number_of_days)
        prs = self.repo.get_pulls(state='closed', base=self.branch, sort='created', direction='desc')
        lead_times = []

        for pr in prs:
            if pr.merged and pr.merged_at > start_date:
                commits = pr.get_commits()
                first_commit_date = commits[0].commit.committer.date if self.commit_counting_method == 'first' else commits[-1].commit.committer.date
                pr_duration = (pr.merged_at - first_commit_date).total_seconds() / 3600.0  # Convert to hours
                lead_times.append(pr_duration)

        return lead_times

    def _calculate_workflow_lead_times(self):
        start_date = datetime.datetime.now() - datetime.timedelta(days=self.number_of_days)
        workflows = self.repo.get_workflows()
        lead_times = []

        for workflow in workflows:
            if workflow.name in self.workflows:
                runs = workflow.get_runs(branch=self.branch)
                for run in runs:
                    if run.status == "completed" and run.created_at > start_date:
                        duration = (run.updated_at - run.created_at).total_seconds() / 3600.0  # Convert to hours
                        lead_times.append(duration)

        return lead_times

    def _determine_rating(self, lead_time_for_changes):
        # Define your thresholds for ratings here
        daily_deployment = 24
        weekly_deployment = 24 * 7
        monthly_deployment = 24 * 30
        six_months_deployment = 24 * 30 * 6

        if lead_time_for_changes < 1:
            return "Elite", "brightgreen"
        elif lead_time_for_changes <= daily_deployment:
            return "High", "green"
        elif lead_time_for_changes <= weekly_deployment:
            return "Medium", "yellow"
        elif lead_time_for_changes <= six_months_deployment:
            return "Low", "orange"
        else:
            return "Poor", "red"

    def display_results(self, results):
        print(f"PR average time duration: {results['PRAverageTimeDuration']} hours")
        print(f"Workflow average time duration: {results['WorkflowAverageTimeDuration']} hours")
        print(f"Lead time for changes in hours: {results['LeadTimeForChangesInHours']}")
        print(f"Rating: {results['Rating']} (Color: {results['Color']})")

# Usage
if __name__ == "__main__":
    owner_repo = os.getenv('REPOSITORY')
    workflows = os.getenv('WORKFLOWS')  # Comma-separated workflow names
    branch = "main"
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS'))
    number_of_days = 30 if not time_frame else time_frame
    commit_counting_method = "last"  # "last" or "first"
    token = os.getenv('GITHUB_TOKEN')  # Replace with your actual token or None for unauthenticated access

    analytics = GitHubAnalytics(owner_repo, workflows, branch, number_of_days, commit_counting_method, token)
    report  = json.dumps(analytics.calculate_lead_times())
    
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"report={report}\n")
