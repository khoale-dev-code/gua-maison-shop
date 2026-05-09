"""
app/services/email_service.py

Gửi email qua Gmail SMTP — không cần dịch vụ bên thứ ba.

Yêu cầu .env:
    MAIL_SENDER_EMAIL=Lekhoale30092003@gmail.com
    MAIL_SENDER_NAME=GUA Maison
    MAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   ← App Password từ Google
    MAIL_SMTP_HOST=smtp.gmail.com           ← mặc định, có thể bỏ qua
    MAIL_SMTP_PORT=587                      ← mặc định, có thể bỏ qua
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _build_reset_email_html(first_name: str, reset_link: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Khôi phục mật khẩu – GUA Maison</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f4ef;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"
       style="background:#f7f4ef;padding:48px 16px;">
  <tr><td align="center">

    <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
           style="max-width:520px;background:#fbfaf8;border:1px solid #d6d3d1;border-left:5px solid #1c1917;">

      <!-- HEADER -->
      <tr>
        <td style="background:#1c1917;padding:28px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td>
                <p style="margin:0 0 3px;font-family:Georgia,'Times New Roman',serif;
                           font-size:9px;font-weight:700;letter-spacing:0.38em;
                           text-transform:uppercase;color:#9d7b3f;">Maison</p>
                <p style="margin:0;font-family:Georgia,'Times New Roman',serif;
                           font-size:22px;font-weight:600;letter-spacing:0.06em;color:#fbfaf8;">GUA</p>
              </td>
              <td align="right">
                <p style="margin:0 0 8px;font-family:Georgia,'Times New Roman',serif;
                           font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:#78716c;">
                  Bảo mật tài khoản
                </p>
                <div style="width:32px;height:1px;background:#9d7b3f;margin-left:auto;"></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- BODY -->
      <tr>
        <td style="padding:40px 40px 24px;">
          <p style="margin:0 0 6px;font-family:Georgia,'Times New Roman',serif;
                     font-size:9px;font-weight:700;letter-spacing:0.32em;
                     text-transform:uppercase;color:#9d7b3f;">Khôi phục tài khoản</p>
          <h1 style="margin:0 0 16px;font-family:Georgia,'Times New Roman',serif;
                      font-size:26px;font-weight:600;line-height:1.2;color:#1c1917;">
            Đặt lại mật khẩu<br>của bạn
          </h1>
          <div style="width:40px;height:2px;background:#9d7b3f;margin-bottom:28px;"></div>

          <p style="margin:0 0 8px;font-family:Georgia,'Times New Roman',serif;
                     font-size:14px;color:#44403c;line-height:1.8;">
            Xin chào <strong style="color:#1c1917;">{first_name}</strong>,
          </p>
          <p style="margin:0 0 32px;font-family:Georgia,'Times New Roman',serif;
                     font-size:13px;color:#78716c;line-height:1.8;">
            Chúng tôi nhận được yêu cầu khôi phục mật khẩu cho tài khoản GUA Maison
            gắn với địa chỉ email này. Nhấn vào nút bên dưới để thiết lập mật khẩu mới.
          </p>

          <!-- CTA -->
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td align="center" style="padding-bottom:32px;">
                <a href="{reset_link}"
                   style="display:inline-block;background:#1c1917;color:#fbfaf8;
                          text-decoration:none;font-family:Georgia,'Times New Roman',serif;
                          font-size:10px;font-weight:700;letter-spacing:0.28em;
                          text-transform:uppercase;padding:18px 44px;
                          border:1px solid #1c1917;">
                  Đặt lại mật khẩu &#8594;
                </a>
              </td>
            </tr>
          </table>

          <!-- Warning -->
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                 style="margin-bottom:28px;">
            <tr>
              <td style="background:#fef9f0;border:1px solid #fde68a;
                         border-left:3px solid #d97706;padding:14px 18px;">
                <p style="margin:0;font-family:Georgia,'Times New Roman',serif;
                           font-size:11px;color:#92400e;line-height:1.7;">
                  <strong>Lưu ý:</strong> Đường dẫn này sẽ hết hạn sau
                  <strong>1 giờ</strong> kể từ khi email được gửi.
                  Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua —
                  tài khoản của bạn vẫn được bảo vệ an toàn.
                </p>
              </td>
            </tr>
          </table>

          <!-- Fallback link -->
          <p style="margin:0 0 4px;font-family:Georgia,'Times New Roman',serif;
                     font-size:10px;color:#a8a29e;line-height:1.6;">
            Nếu nút không hoạt động, sao chép liên kết sau vào trình duyệt:
          </p>
          <p style="margin:0;font-family:'Courier New',Courier,monospace;
                     font-size:10px;color:#9d7b3f;word-break:break-all;line-height:1.6;">
            {reset_link}
          </p>
        </td>
      </tr>

      <!-- DIVIDER -->
      <tr>
        <td style="padding:0 40px;">
          <div style="height:1px;background:#e7e5e4;"></div>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="padding:20px 40px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td>
                <p style="margin:0 0 4px;font-family:Georgia,'Times New Roman',serif;
                           font-size:9px;font-weight:700;letter-spacing:0.3em;
                           text-transform:uppercase;color:#9d7b3f;">GUA Maison</p>
                <p style="margin:0 0 2px;font-family:Georgia,'Times New Roman',serif;
                           font-size:10px;color:#a8a29e;line-height:1.6;">
                  Email tự động — vui lòng không trả lời email này.
                </p>
                <p style="margin:0;font-family:Georgia,'Times New Roman',serif;
                           font-size:10px;color:#d6d3d1;">
                  &copy; 2025 GUA Maison. All rights reserved.
                </p>
              </td>
              <td align="right" valign="bottom">
                <div style="width:28px;height:28px;background:#1c1917;
                            text-align:center;line-height:28px;">
                  <span style="font-family:Georgia,'Times New Roman',serif;
                               font-size:11px;font-weight:700;color:#9d7b3f;">G</span>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_password_reset_email(recipient_email: str, recipient_name: str, reset_link: str) -> bool:
    """
    Gửi email khôi phục mật khẩu qua Gmail SMTP.

    Args:
        recipient_email: Email người nhận.
        recipient_name:  Tên đầy đủ người nhận.
        reset_link:      Link reset password (hết hạn sau 1 giờ).

    Returns:
        True nếu gửi thành công, False nếu thất bại.
    """
    smtp_host = os.environ.get("MAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("MAIL_SMTP_PORT", 587))
    sender_email = os.environ.get("MAIL_SENDER_EMAIL")
    sender_name = os.environ.get("MAIL_SENDER_NAME", "GUA Maison")
    app_password = os.environ.get("MAIL_APP_PASSWORD")

    if not sender_email or not app_password:
        logger.error("[EMAIL] MAIL_SENDER_EMAIL hoặc MAIL_APP_PASSWORD chưa được cấu hình.")
        return False

    first_name = recipient_name.split()[0] if recipient_name else "Quý khách"

    # Tạo email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[GUA Maison] Khôi phục mật khẩu của bạn"
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = recipient_email

    html_body = _build_reset_email_html(first_name, reset_link)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()  # mã hóa kết nối
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())

        logger.info(f"[EMAIL] Sent reset email → {recipient_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("[EMAIL] Xác thực Gmail thất bại — kiểm tra lại MAIL_APP_PASSWORD trong .env")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"[EMAIL] SMTP error khi gửi đến {recipient_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"[EMAIL] Lỗi không xác định khi gửi đến {recipient_email}: {e}")
        return False
