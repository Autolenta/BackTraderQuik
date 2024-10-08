import logging  # Будем вести лог
from collections import deque
from datetime import datetime

from backtrader.metabase import MetaParams
from backtrader.utils.py3 import with_metaclass

from QuikPy import QuikPy


class MetaSingleton(MetaParams):
    """Метакласс для создания Singleton классов"""
    def __init__(cls, *args, **kwargs):
        """Инициализация класса"""
        super(MetaSingleton, cls).__init__(*args, **kwargs)
        cls._singleton = None  # Экземпляра класса еще нет

    def __call__(cls, *args, **kwargs):
        """Вызов класса"""
        if not cls._singleton:  # Если класса нет в экземплярах класса
            cls._singleton = super(MetaSingleton, cls).__call__(*args, **kwargs)  # то создаем зкземпляр класса
        return cls._singleton  # Возвращаем экземпляр класса


class QKStore(with_metaclass(MetaSingleton, object)):
    """Хранилище QUIK"""
    logger = logging.getLogger('QKStore')  # Будем вести лог

    BrokerCls = None  # Класс брокера будет задан из брокера
    DataCls = None  # Класс данных будет задан из данных

    @classmethod
    def getdata(cls, *args, **kwargs):
        """Returns DataCls with args, kwargs"""
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        """Returns broker with *args, **kwargs from registered BrokerCls"""
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self, provider=QuikPy()):
        super(QKStore, self).__init__()
        self.notifs = deque()  # Уведомления хранилища
        self.provider = provider  # Подключаемся ко всем торговым счетам
        self.new_bars = []  # Новые бары по всем подпискам на тикеры из QUIK

    def start(self):
        self.provider.on_connected = lambda data: self.logger.info(data)  # Соединение терминала с сервером QUIK
        self.provider.on_disconnected = lambda data: self.logger.info(data)  # Отключение терминала от сервера QUIK
        self.provider.on_new_candle = self.on_new_candle  # Обработчик новых баров по подписке из QUIK

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        """Выдача уведомлений хранилища"""
        self.notifs.append(None)
        return [notif for notif in iter(self.notifs.popleft, None)]

    def stop(self):
        self.provider.on_new_candle = self.provider.default_handler  # Возвращаем обработчик по умолчанию
        self.provider.close_connection_and_thread()  # Закрываем соединение для запросов и поток обработки функций обратного вызова

    def on_new_candle(self, data):
        bar = data['data']  # Данные бара
        class_code = bar['class']  # Код режима торгов
        sec_code = bar['sec']  # Тикер
        interval = bar['interval']  # Временной интервал QUIK
        datetime = self.get_bar_open_date_time(bar)
        _open = self.provider.quik_price_to_price(class_code, sec_code, bar['open'])
        high = self.provider.quik_price_to_price(class_code, sec_code, bar['high'])
        low = self.provider.quik_price_to_price(class_code, sec_code, bar['low'])
        close = self.provider.quik_price_to_price(class_code, sec_code, bar['close'])
        volume = self.provider.lots_to_size(class_code, sec_code, int(bar['volume']))
        bar = dict(datetime=datetime, open=_open, high=high, low=low, close=close, volume=volume)  # Новый бар
        self.new_bars.append(dict(guid=(class_code, sec_code, interval), data=bar))

    @staticmethod
    def get_bar_open_date_time(bar):
        """Дата и время открытия бара"""
        dt_json = bar['datetime']  # Получаем составное значение даты и времени открытия бара
        return datetime(dt_json['year'], dt_json['month'], dt_json['day'], dt_json['hour'], dt_json['min'])  # Время открытия бара
