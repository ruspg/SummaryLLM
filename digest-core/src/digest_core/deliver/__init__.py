"""Delivery targets for the digest pipeline."""

from digest_core.deliver.mattermost import MattermostDeliverer, ping_mattermost_webhook

__all__ = ["MattermostDeliverer", "ping_mattermost_webhook"]
