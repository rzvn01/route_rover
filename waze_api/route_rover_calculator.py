import re

import requests
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

from project.waze_api.route_error import RouteError


def coordinates_string_parser(coordinates):
    lat, lon = coordinates.split(',')
    print(lat, "\t", lon)
    return {"lat": lat.strip(), "lon": lon.strip(), "bounds": {}}


def verify_address(coordinates):
    COORD_MATCHER = re.compile(r'^([-+]?)([\d]{1,2})(((\.)(\d+)(,)))(\s*)(([-+]?)([\d]{1,3})((\.)(\d+))?)$')

    matched = re.search(COORD_MATCHER, coordinates)
    return matched is not None


class RouteCalculator:
    WAZE_URL = "https://www.waze.com/"
    HEADERS = {
        "User-Agent": "Chrome/91.0.4472.124",
        "referer": WAZE_URL,
    }
    VEHICLE_TYPES = ('TAXI', 'MOTORCYCLE')
    BASE_COORDINATE = {
        'US': {"lat": 40.713, "lon": -74.006},
        'EU': {"lat": 47.498, "lon": 19.040},
        'IL': {"lat": 31.768, "lon": 35.214},
        'AU': {"lat": -35.281, "lon": 149.128}
    }
    COORDINATE_SERVERS = {
        'US': 'SearchServer/mozi',
        'EU': 'row-SearchServer/mozi',
        'IL': 'il-SearchServer/mozi',
        'AU': 'row-SearchServer/mozi'
    }
    ROUTING_SERVERS = {
        'US': 'RoutingManager/routingRequest',
        'EU': 'row-RoutingManager/routingRequest',
        'IL': 'il-RoutingManager/routingRequest',
        'AU': 'row-RoutingManager/routingRequest'
    }

    def __init__(self, start_address, end_address, region='EU', vehicle='', avoid_toll_roads=False,
                 avoid_subscription_roads=False, avoid_ferries=False):
        self.region = region.upper()
        if vehicle and vehicle in self.VEHICLE_TYPES:
            self.vehicle = vehicle.upper()
        else:
            self.vehicle = 'MOTORCYCLE'

        self.avoid_toll_roads = avoid_toll_roads
        self.avoid_ferries = avoid_ferries

        self.ROUTE_OPTIONS = {
            'AVOID_TRAILS': 't',
            'AVOID_TOLL_ROADS': 't' if avoid_toll_roads else 'f',
            'AVOID_FERRIES': 't' if avoid_ferries else 'f'
        }

        self.avoid_subscription_roads = avoid_subscription_roads

        if verify_address(start_address):
            self.start_coordinates = coordinates_string_parser(start_address)
        else:
            self.start_coordinates = self.address_to_coordinates(start_address)

        if verify_address(end_address):
            self.end_coordinates = coordinates_string_parser(end_address)
        else:
            self.end_coordinates = self.address_to_coordinates(end_address)

    def address_to_coordinates(self, address):

        base_coordinates = self.BASE_COORDINATE[self.region]
        get_cord = self.COORDINATE_SERVERS[self.region]
        url_options = {
            "q": address,
            "lang": "eng",
            "origin": "livemap",
            "lat": base_coordinates["lat"],
            "lon": base_coordinates["lon"]
        }

        response = requests.get(self.WAZE_URL + get_cord, params=url_options, headers=self.HEADERS)

        for response_json in response.json():
            if response_json.get('city'):
                lat = response_json['location']['lat']
                lon = response_json['location']['lon']
                bounds = response_json['bounds']
                if bounds is not None:
                    bounds['top'], bounds['bottom'] = max(bounds['top'], bounds['bottom']), min(bounds['top'],
                                                                                                bounds['bottom'])
                    bounds['left'], bounds['right'] = min(bounds['left'], bounds['right']), max(bounds['left'],
                                                                                                bounds['right'])
                else:
                    bounds = {}
                return {"lat": lat, "lon": lon, "bounds": bounds}

        try:
            geolocator = Nominatim(user_agent="Wazy")
            location = geolocator.geocode(address, language="en", timeout=10)
            if location:
                return {"lat": location.latitude, "lon": location.longitude, "bounds": {}}
        except GeocoderTimedOut:
            pass
        raise RouteError("Cannot get coordinates for %s" % address)

    @staticmethod
    def _check_response(response):
        """Check waze server response."""
        if response.ok:
            try:
                return response.json()
            except ValueError:
                return None

    def get_route(self, path_number=1, delta_time=0):
        routing_server = self.ROUTING_SERVERS[self.region]

        url_options = {
            "from": "x:%s y:%s" % (self.start_coordinates["lon"], self.start_coordinates["lat"]),
            "to": "x:%s y:%s" % (self.end_coordinates["lon"], self.end_coordinates["lat"]),
            "at": delta_time,
            "returnJSON": "true",
            "returnGeometries": "true",
            "returnInstructions": "true",
            "timeout": 60000,
            "nPaths": path_number,
            "options": ','.join('%s:%s' % (opt, value) for (opt, value) in self.ROUTE_OPTIONS.items()),
            "vehicleType": self.vehicle,
            "subscription": "*" if self.avoid_subscription_roads is False else ""  # TODO daca merge sau nu asa
        }

        response = requests.get(self.WAZE_URL + routing_server, params=url_options, headers=self.HEADERS)
        response.encoding = 'utf-8'
        response_json = self._check_response(response)

        if response_json:
            if 'error' in response_json:
                raise RouteError(response_json.get("error"))
            else:
                if response_json.get("alternatives"):
                    return [alt['response'] for alt in response_json['alternatives']]
                response = response_json['response']
                if isinstance(response, list):
                    response = response[0]
                if path_number > 1:
                    return [response]
                return response
        else:
            raise RouteError("API call returned empty response")

    def _add_up_route(self, results, real_time=True, stop_at_bounds=False):

        start_bounds = self.start_coordinates['bounds']
        end_bounds = self.end_coordinates['bounds']

        def between(target, min, max):
            return min < target < max

        time = 0
        distance = 0

        for segment in results:
            if stop_at_bounds and segment.get('path'):
                x = segment['path']['x']
                y = segment['path']['y']
                if (
                        between(x, start_bounds.get('left', 0), start_bounds.get('right', 0)) or
                        between(x, end_bounds.get('left', 0), end_bounds.get('right', 0))
                ) and (
                        between(y, start_bounds.get('bottom', 0), start_bounds.get('top', 0)) or
                        between(y, end_bounds.get('bottom', 0), end_bounds.get('top', 0))
                ):
                    continue
            if 'crossTime' in segment:
                time += segment['crossTime' if real_time else 'crossTimeWithoutRealTime']
            else:
                time += segment['cross_time' if real_time else 'cross_time_without_real_time']
            distance += segment['length']

        route_time = time / 60.0  # return time in hours
        route_distance = distance / 1000.0  # return distance in km

        return route_time, route_distance

    def calc_route_info(self, real_time=True, stop_at_bounds=False, delta_time=0):

        route = self.get_route(1, delta_time)
        results = route['results' if 'results' in route else 'result']
        route_time, route_distance = self._add_up_route(results, real_time=real_time, stop_at_bounds=stop_at_bounds)
        print(f'Time {route_time.__format__(".2f")} minutes, distance {route_distance.__format__(".2f")} km.')
        return route_time, route_distance
