"""SMTP diagnostics without logging credentials or message contents."""

import logging

from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

logger = logging.getLogger('passing.mail')


class EmailBackend(SMTPBackend):
    def open(self):
        logger.debug(
            'SMTP connection: host=%s port=%s TLS=%s SSL=%s auth=%s timeout=%s',
            self.host, self.port, self.use_tls, self.use_ssl,
            bool(self.username), self.timeout,
        )
        try:
            result = super().open()
        except Exception as error:
            self.log_error('connection/authentication', error)
            raise
        if self.connection is None:
            logger.error('SMTP connection unavailable (fail_silently=%s)', self.fail_silently)
        else:
            logger.debug('SMTP connection ready')
        return result

    def _send(self, email_message):
        logger.debug('SMTP sending message: recipients=%s', len(email_message.recipients()))
        try:
            sent = super()._send(email_message)
        except Exception as error:
            self.log_error('send', error)
            raise
        if sent:
            logger.info('SMTP server accepted message; inbox delivery is not guaranteed')
        else:
            logger.warning('SMTP message not sent (fail_silently=%s)', self.fail_silently)
        return sent

    @staticmethod
    def log_error(stage, error):
        # Server replies and exception strings may contain addresses or message data.
        code = getattr(error, 'smtp_code', None)
        logger.error(
            'SMTP failure: stage=%s error=%s smtp_code=%s errno=%s',
            stage, type(error).__name__, code if isinstance(code, int) else None,
            getattr(error, 'errno', None),
        )
