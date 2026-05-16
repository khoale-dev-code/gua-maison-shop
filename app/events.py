# app/events.py
from blinker import signal

# Khai báo các sự kiện trong hệ thống
order_completed_event = signal('order-completed')
review_submitted_event = signal('review-submitted')
