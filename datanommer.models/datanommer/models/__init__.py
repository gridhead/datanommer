from sqlalchemy import create_engine
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    ForeignKey,
    UnicodeText,
)

from sqlalchemy.orm import (
        sessionmaker,
        scoped_session,
        relationship,
        mapper
)

from sqlalchemy.schema import Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property

import datetime
import fedmsg.encoding

maker = sessionmaker()
session = scoped_session(maker)

DeclarativeBase = declarative_base()
DeclarativeBase.query = session.query_property()

import logging
log = logging.getLogger("datanommer")


def init(uri=None, alembic_ini=None, create=False):
    """ Initialize a connection.  Create tables if requested."""

    if uri is None:
        uri = 'sqlite:////tmp/datanommer.db'
        log.warning("No db uri given.  Using %r" % uri)

    engine = create_engine(uri)
    session.configure(bind=engine)
    DeclarativeBase.query = session.query_property()

    # Loads the alembic configuration and generates the version table, with
    # the most recent revision stamped as head
    if alembic_ini is not None:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

    if create:
        DeclarativeBase.metadata.create_all(engine)


def add(message):
    """ Take a dict-like fedmsg message and store it in the table.
    """

    if len(message['topic']) == 0:
        model_cls = UnclassifiedMessage
    else:
        model_cls = Message

    timestamp = message['timestamp']
    try:
        timestamp = datetime.datetime.fromtimestamp(timestamp)
    except Exception:
        pass
    print('Timestamped')

    obj = model_cls(
        i=message['i'],
        topic=message['topic'],
        timestamp=timestamp,
        certificate=message.get('certificate', None),
        signature=message.get('signature', None),
    )
    print('Topic is %r' %obj.topic)

    usernames = fedmsg.meta.msg2usernames(message)
    packages = fedmsg.meta.msg2packages(message)
    obj.msg = message['msg']

    session.add(obj)

    # TODO -- can we avoid committing every time?
    session.flush()
    session.commit()

class BaseMessage(object):
    id = Column(Integer, primary_key=True)
    i = Column(Integer, nullable=False)
    topic = Column(UnicodeText, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    certificate = Column(UnicodeText)
    signature = Column(UnicodeText)
    _msg = Column(UnicodeText, nullable=False)

    @hybrid_property
    def msg(self):
        return fedmsg.encoding.loads(self._msg)

    @msg.setter
    def msg(self, dict_like_msg):
        self._msg = fedmsg.encoding.dumps(dict_like_msg)

    def __json__(self):
        return dict(
            i=self.i,
            topic=self.topic,
            timestamp=self.timestamp,
            certificate=self.certificate,
            signature=self.signature,
            msg=self.msg,
        )

class User(DeclarativeBase):
    __tablename__ = 'user'
    name = Column(UnicodeText, primary_key=True)

class Packages(DeclarativeBase):
    __tablename__ = 'package'
    name = Column(UnicodeText, primary_key=True)

class Message(DeclarativeBase, BaseMessage):
    __tablename__ = "messages"

#
class UnclassifiedMessage(DeclarativeBase, BaseMessage):
    topic_filter = "this will never be in a topic..."
    __tablename__ = "unclassified_messages"
#
#
models = frozenset((
    v for k, v in locals().items()
    if (
        isinstance(v, type) and
        issubclass(v, BaseMessage) and
        k is not "BaseMessage"
    )
))
