import os
from github import Github, Team, PullRequest,GithubException
import datetime
import json
import logging
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Any, Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TeamMetrics:
    def __init__(
        self, owner: str, repo: str, timeframe: int, team_name: str, pat_token: str, base_url: str | None
    ) -> None:
        try:
            self.github_client = Github(login_or_token=pat_token, base_url=base_url) if base_url else Github(pat_token)
            self.repo = self.github_client.get_repo(f"{owner}/{repo}")
        except GithubException as e:
            logging.error(f"Failed to initialize GitHub client: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error during initialization: {e} - verify that your github credentials are valid")
            raise

        self.team_slug = self.convert_to_slug(team_name)
        self.timeframe = timeframe
        self.start_date = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(days=self.timeframe)
        self.semaphore = threading.Semaphore(5)  # Limit concurrent requests
        self.team_members = self.get_team_members()

    @staticmethod
    def convert_to_slug(name: str) -> str:
        """Convert a team name to a slug by replacing spaces with hyphens and lowercasing."""
        return re.sub(r"\s+", "-", name.strip()).lower()

    def get_team_members(self) -> List[str]:
        try:
            logging.info(f"Fetching team members for {self.team_slug}")
            team = self.github_client.get_organization(
                self.repo.owner.login
            ).get_team_by_slug(self.team_slug)
            return [member.login for member in team.get_members()]
        
        except GithubException as e:
            logging.error(f"Failed to fetch team members: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while fetching team members: {e}")
            raise

    def calculate_metrics(self) -> Dict[str, Any]:
        try:
            prs = self.repo.get_pulls(state="all", sort="created", direction="desc")
            filtered_prs: List[PullRequest.PullRequest] = [
                pr for pr in prs if pr.created_at >= self.start_date
            ]
            logging.info(
                f"Fetched {len(filtered_prs)} pull requests for the specified timeframe"
            )

            logging.info(f"Fetching team info for {self.repo.full_name}/{self.team_slug}")
            response_rate, response_time = self.calculate_response_metrics(filtered_prs)
            team_info = self.get_team_info()
            return {**response_rate, **response_time, **team_info}
        except GithubException as e:
            logging.error(f"Failed to calculate metrics: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while calculating metrics: {e}")
            raise

    def get_team_info(self) -> Dict[str, Any]:
        try:
            logging.info(f"Fetching team info from {self.repo.owner.login} organization")
            team:Team.Team = self.github_client.get_organization(
                self.repo.owner.login
            ).get_team_by_slug(self.team_slug)
            return {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "members_count": team.members_count,
                "repos_count": team.repos_count,
                "slug": team.slug,
                "link": team.html_url,
                "permission": team.permission,
                "notification_setting": team.notification_setting,
            }
        except GithubException as e:
            logging.error(f"Failed to fetch team info: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while fetching team info: {e}")
            raise

    def calculate_response_metrics(
        self, prs: List[PullRequest.PullRequest]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        logging.info("Calculating response rate and time")
        total_requests = 0
        responded_requests = 0
        total_response_time = datetime.timedelta(0)
        total_responses = 0

        def fetch_reviews(pr: PullRequest.PullRequest) -> None:
            nonlocal responded_requests, total_response_time, total_responses, total_requests
            try:
                with self.semaphore:  # Ensure limited concurrent requests
                    # Check if the team was explicitly requested to review the PR
                    if any(team.slug == self.team_slug for team in pr.requested_teams):
                        total_requests += 1
                        reviews = pr.get_reviews()
                        for review in reviews:
                            if review.user.login in self.team_members:
                                responded_requests += 1
                                response_time = review.submitted_at - pr.created_at
                                total_response_time += response_time
                                total_responses += 1
                                break
            except GithubException as e:
                logging.error(f"Failed to fetch reviews for PR {pr.number}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error while fetching reviews for PR {pr.number}: {e}")

        try:

            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_pr = {executor.submit(fetch_reviews, pr): pr for pr in prs}
                for future in as_completed(future_to_pr):
                    pass
        
        except Exception as e:
            logging.error(f"Unexpected error in ThreadPoolExecutor: {e}")
            raise

        response_rate = (
            (responded_requests / total_requests) * 100 if total_requests else 0
        )
        average_response_time = (
            self.timedelta_to_decimal_hours(total_response_time / total_responses)
            if total_responses
            else 0
        )

        logging.info(f"Successfully retrieved team response metrics")
        return {"response_rate": round(response_rate, 2)}, {
            "average_response_time": average_response_time
        }

    @staticmethod
    def timedelta_to_decimal_hours(td: datetime.timedelta) -> float:
        return round(td.total_seconds() / 3600, 2)


if __name__ == "__main__":
    import time

    start_time = time.time()

    parser = argparse.ArgumentParser(
        description="Calculate Team Metrics for Pull Requests."
    )
    parser.add_argument("--owner", required=True, help="Owner of the repository")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--timeframe", type=int, default=30, help="Timeframe in days")
    parser.add_argument(
        "--team", required=True, help="Team name to calculate metrics for"
    )
    parser.add_argument(
        "--platform",
        default="github-actions",
        choices=["github-actions", "self-hosted"],
        help="CI/CD platform type",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for self-hosted GitHub instance (e.g., https://github.example.com/api/v3)",
        default= None
    )

    args = parser.parse_args()

    try:
        logging.info(f"Repository Name: {args.owner}/{args.repo}")
        logging.info(f"TimeFrame (in days): {args.timeframe}")
        logging.info(f"Team Name: {args.team}")
        
        team_metrics = TeamMetrics(
            args.owner, args.repo, args.timeframe, args.team, pat_token=args.token, base_url= args.base_url
        )
        metrics = team_metrics.calculate_metrics()
        metrics_json = json.dumps(metrics, default=str)
        logging.info(f"Team info: {metrics_json}")

        if args.platform == "github-actions":
            with open(os.getenv("GITHUB_ENV", ""), "a") as github_env:
                github_env.write(f"team_metrics={metrics_json}\n")

        logging.info(f"Execution Time: {time.time() - start_time}")

    except Exception as e:
        logging.error(f"Failed to execute script: {e}")
