"""Smart mirror app.

-Uses weather information from openweathermap.org,
you can create an account at https://home.openweathermap.org/users/sign_up
-News from the Google News.
"""

# Utils imports
import time
import locale
import threading
import json
import traceback
from contextlib import contextmanager
from tkinter import (
    Frame,
    Label,
    BOTH,
    LEFT,
    RIGHT,
    TOP,
    BOTTOM,
    YES,
    W,
    E,
    N,
    S,
    Tk
)

# Third party imports
import requests
import feedparser
from PIL import Image, ImageTk


LOCALE_LOCK = threading.Lock()

# Constants
UI_LOCALE = ''
TIME_FORMAT = 12
DATE_FORMAT = "%b %d, %Y"
NEWS_COUNTRY_CODE = 'es-AR'
NEWS_URL = 'https://news.google.com/rss?hl'
WEATHER_API_TOKEN = ''
WEATHER_LANG = 'en'
WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'
GEOIP_API_TOKEN = ''
LATITUDE = -26.6316062
LONGITUDE = -54.1174863
XLARGE_TEXT_SIZE = 90
LARGE_TEXT_SIZE = 44
MEDIUM_TEXT_SIZE = 24
SMALL_TEXT_SIZE = 14


@contextmanager
def setlocale(name):
    """thread proof function to work with locale."""
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


# maps open weather icons
icon_lookup = {
    '01d': "assets/Sun.png",  # clear sky day
    '01n': "assets/Moon.png",  # clear sky night
    '02d': "assets/PartlySunny.png",  # few clouds day
    '02n': "assets/PartlyMoon.png",  # few clouds night
    '03d': "assets/Cloud.png",  # scattered clouds day
    '03n': "assets/Cloud.png",  # scattered clouds night
    '04d': "assets/Cloud.png",  # broken clouds day
    '04n': "assets/Cloud.png",  # broken clouds night
    '09d': "assets/Rain.png",  # shower rain day
    '09n': "assets/Rain.png",  # shower rain night
    '10d': "assets/Rain.png",  # rain day
    '10n': "assets/Rain.png",  # rain night
    '11d': "assets/Storm.png",  # thunderstorm day
    '11n': "assets/Storm.png",  # thunderstorm night
    '13d': "assets/Snow.png",  # snow day
    '13n': "assets/Snow.png",  # snow night
    '50d': "assets/Haze.png",  # mist day
    '50n': "assets/Haze.png",  # mist night
}


class Clock(Frame):
    """Display a clock in the window."""
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')

        # initialize time label
        self.time_old = ''
        self.time_lbl = Label(
            self, font=('monospace', LARGE_TEXT_SIZE),
            fg="white", bg="black"
        )
        self.time_lbl.pack(side=TOP, anchor=E)

        # initialize day of week
        self.day_of_week_old = ''
        self.day_of_wk_lbl = Label(
            self, text=self.day_of_week_old,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.day_of_wk_lbl.pack(side=TOP, anchor=E)

        # initialize date label
        self.date_old = ''
        self.date_lbl = Label(
            self, text=self.date_old,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white", bg="black"
        )

        self.date_lbl.pack(side=TOP, anchor=E)
        self.tick()

    def tick(self):
        """Tick the clock."""
        with setlocale(UI_LOCALE):
            if TIME_FORMAT == 12:
                time_updated = time.strftime('%I:%M%p')  # hour in 12h format
            else:
                time_updated = time.strftime('%H:%M')  # hour in 24h format

            day_of_week_updated = time.strftime('%A')
            date_updated = time.strftime(DATE_FORMAT)

            # if time string has changed, update it
            if time_updated != self.time_old:
                self.time_old = time_updated
                self.time_lbl.config(text=time_updated)
            if day_of_week_updated != self.day_of_week_old:
                self.day_of_week_old = day_of_week_updated
                self.day_of_wk_lbl.config(text=day_of_week_updated)
            if date_updated != self.date_old:
                self.date_old = date_updated
                self.date_lbl.config(text=date_updated)
            # calls itself every 200 milliseconds
            # to update the time display as needed
            # could use >200 ms, but display gets jerky
            self.time_lbl.after(200, self.tick)


class Weather(Frame):
    """Display openweathermap.org weather information on window."""

    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        self.temperature = ''
        self.forecast = ''
        self.actual_location = ''
        self.currently = ''
        self.icon = ''

        self.degree_frm = Frame(self, bg="black")
        self.degree_frm.pack(side=TOP, anchor=W)
        self.temperature_lbl = Label(
            self.degree_frm,
            font=('monospace', XLARGE_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.temperature_lbl.pack(side=LEFT, anchor=N)

        self.icon_lbl = Label(self.degree_frm, bg="black")
        self.icon_lbl.pack(side=LEFT, anchor=N, padx=20)
        self.currently_lbl = Label(
            self,
            font=('monospace', MEDIUM_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.currently_lbl.pack(side=TOP, anchor=W)
        self.forecast_lbl = Label(
            self,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.forecast_lbl.pack(side=TOP, anchor=W)
        self.actual_location_lbl = Label(
            self,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.actual_location_lbl.pack(side=TOP, anchor=W)
        self.get_weather()

    def get_ip(self):
        """Get your ip."""
        try:
            ip_url = "http://jsonip.com/"
            req = requests.get(ip_url)
            ip_json = req.json()
            return ip_json['ip']
        except (json.decoder.JSONDecodeError, KeyError):
            traceback.print_exc()
            return "Error: Cannot get ip."

    def get_weather(self):
        """Get weather method."""

        try:
            if LATITUDE is None and LONGITUDE is None:
                # get actual_location
                actual_location_req_url = f'https://api.freegeoip.app/json\
                    /{self.get_ip()}?apikey={GEOIP_API_TOKEN}'

                request = requests.get(actual_location_req_url)
                actual_location_obj = json.loads(request.text)

                lat = actual_location_obj['latitude']
                lon = actual_location_obj['longitude']

                actual_location2 = "%s, %s" % (
                    actual_location_obj['city'],
                    actual_location_obj['region_code']
                )

                # get weather
                weather_req_url = f"{WEATHER_API_URL}?lat={lat}&\
                    lon={lon}&lang={WEATHER_LANG}&appid={WEATHER_API_TOKEN}"

            else:
                # get weather
                weather_req_url = f"{WEATHER_API_URL}?lat={LATITUDE}&lon={LONGITUDE}&\
                    lang={WEATHER_LANG}&appid={WEATHER_API_TOKEN}"

            request = requests.get(weather_req_url)
            weather_obj = request.json()

            degree_sign = u'\N{DEGREE SIGN}'

            celsius_temp = self.convert_kelvin_to_celsius(
                int(weather_obj['main']['temp'])
            )
            temperature2 = "%s%s" % (str(celsius_temp), degree_sign)

            currently2 = weather_obj['weather'][0]['main']
            forecast2 = weather_obj['weather'][0]['description']

            actual_location2 = weather_obj['name']
            icon_id = weather_obj['weather'][0]['icon']

            icon2 = icon_lookup.get(icon_id, None) or None

            if icon2 is not None:
                if self.icon != icon2:
                    self.icon = icon2
                    image = Image.open(icon2)
                    image = image.resize((100, 100), Image.ANTIALIAS)
                    image = image.convert('RGB')
                    photo = ImageTk.PhotoImage(image)

                    self.icon_lbl.config(image=photo)
                    self.icon_lbl.image = photo
            else:
                # remove image
                self.icon_lbl.config(image='')

            if self.currently != currently2:
                self.currently = currently2
                self.currently_lbl.config(text=currently2)
            if self.forecast != forecast2:
                self.forecast = forecast2
                self.forecast_lbl.config(text=forecast2)
            if self.temperature != temperature2:
                self.temperature = temperature2
                self.temperature_lbl.config(text=temperature2)
            if self.actual_location != actual_location2:
                if actual_location2 == ", ":
                    self.actual_location = "Cannot Pinpoint Location"
                    self.actual_location_lbl.config(text="Cannot Pinpoint Location")
                else:
                    self.actual_location = actual_location2
                    self.actual_location_lbl.config(text=actual_location2)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: {e}. Cannot get weather.")

        self.after(600000, self.get_weather)

    @staticmethod
    def convert_kelvin_to_fahrenheit(kelvin_temp):
        """This method converts kelvin to fahrenheit."""
        return 1.8 * (kelvin_temp - 273) + 32

    @staticmethod
    def convert_kelvin_to_celsius(kelvin_temp):
        """This method converts a temperature from Kelvin to Celsius."""
        return kelvin_temp - 273


class News(Frame):
    """Display news title from google news."""
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, *args, **kwargs)
        self.config(bg='black')
        self.title = 'News'
        self.news_lbl = Label(
            self,
            text=self.title,
            font=('monospace', MEDIUM_TEXT_SIZE),
            fg="white",
            bg="black"
        )
        self.news_lbl.pack(side=TOP, anchor=W)
        self.headlines_container = Frame(self, bg="black")
        self.headlines_container.pack(side=TOP)
        self.get_headlines()

    def get_headlines(self):
        try:
            # remove all children
            for widget in self.headlines_container.winfo_children():
                widget.destroy()
            if NEWS_COUNTRY_CODE is None:
                headlines_url = f'{NEWS_URL}=en-US'
            else:
                headlines_url = f'{NEWS_URL}={NEWS_COUNTRY_CODE}'

            feed = feedparser.parse(headlines_url)

            for post in feed.entries[0:5]:
                headline = NewsHeadline(self.headlines_container, post.title)
                headline.pack(side=TOP, anchor=W)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: {e}. Cannot get news.")

        self.after(600000, self.get_headlines)


class NewsHeadline(Frame):
    """Create news headline."""
    def __init__(self, parent, event_name=""):
        Frame.__init__(self, parent, bg='black')

        image = Image.open("assets/Newspaper.png")
        image = image.resize((25, 25), Image.ANTIALIAS)
        image = image.convert('RGB')
        photo = ImageTk.PhotoImage(image)

        self.icon_lbl = Label(self, bg='black', image=photo)
        self.icon_lbl.image = photo
        self.icon_lbl.pack(side=LEFT, anchor=N)

        self.event_name = event_name
        self.event_name_lbl = Label(
            self, text=self.event_name,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white", bg="black"
        )
        self.event_name_lbl.pack(side=LEFT, anchor=N)


class Calendar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        self.title = 'Calendar Events'
        self.calendar_lbl = Label(
            self, text=self.title,
            font=('monospace', MEDIUM_TEXT_SIZE),
            fg="white", bg="black"
        )
        self.calendar_lbl.pack(side=TOP, anchor=E)
        self.calendar_event_container = Frame(self, bg='black')
        self.calendar_event_container.pack(side=TOP, anchor=E)
        self.get_events()

    def get_events(self):
        #TODO: implement this method
        # reference https://developers.google.com/google-apps/calendar/quickstart/python

        # remove all children
        for widget in self.calendar_event_container.winfo_children():
            widget.destroy()

        calendar_event = CalendarEvent(self.calendar_event_container)
        calendar_event.pack(side=TOP, anchor=E)
        pass


class CalendarEvent(Frame):
    def __init__(self, parent, event_name="Event 1"):
        Frame.__init__(self, parent, bg='black')
        self.event_name = event_name
        self.event_name_lbl = Label(
            self, text=self.event_name,
            font=('monospace', SMALL_TEXT_SIZE),
            fg="white", bg="black"
        )
        self.event_name_lbl.pack(side=TOP, anchor=E)


class FullscreenWindow:
    """Instanciate a full screen window using tkinter."""

    def __init__(self):
        self.tk = Tk()
        self.tk.configure(background='black')
        self.top_frame = Frame(self.tk, background='black')
        self.bottom_frame = Frame(self.tk, background='black')
        self.top_frame.pack(side=TOP, fill=BOTH, expand=YES)
        self.bottom_frame.pack(side=BOTTOM, fill=BOTH, expand=YES)
        self.state = False
        self.tk.bind("<Return>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        # clock
        self.clock = Clock(self.top_frame)
        self.clock.pack(side=RIGHT, anchor=N, padx=100, pady=60)
        # weather
        self.weather = Weather(self.top_frame)
        self.weather.pack(side=LEFT, anchor=N, padx=100, pady=60)
        # news
        self.news = News(self.bottom_frame)
        self.news.pack(side=LEFT, anchor=S, padx=100, pady=60)
        # calender - removing for now
        # self.calender = Calendar(self.bottom_frame)
        # self.calender.pack(side = RIGHT, anchor=S, padx=100, pady=60)

    def toggle_fullscreen(self, event=None):
        """Toogle fullscreen status."""
        self.state = not self.state  # Just toggling the boolean
        self.tk.attributes("-fullscreen", self.state)
        return "break"

    def end_fullscreen(self, event=None):
        """End fullscreen status."""
        self.state = False
        self.tk.attributes("-fullscreen", False)
        return "break"


if __name__ == '__main__':
    w = FullscreenWindow()
    w.tk.mainloop()
