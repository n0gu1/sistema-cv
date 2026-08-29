from reclutamiento.notifications import unread_notification_count


def notifications(request):
    return {
        "unread_notification_count": unread_notification_count(
            getattr(request, "user", None)
        )
    }
