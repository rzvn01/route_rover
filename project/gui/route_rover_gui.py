from tkinter import ttk

import customtkinter
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from tkintermapview import TkinterMapView

from project.gui.trip_database import TripInfoDatabase
from project.waze_api.route_rover_calculator import RouteCalculator
from project.waze_api.route_error import RouteError

customtkinter.set_default_color_theme("dark-blue")

APP_NAME = "RouteRover"
WIDTH = 1200
HEIGHT = 800
trip_window = None


def get_address_from_coordinates(x):
    latitude = x.position[0]
    longitude = x.position[1]
    try:
        geolocator = Nominatim(user_agent="Wazy")
        location = geolocator.reverse((latitude, longitude), language="en")
        if location and location.address:
            address_parts = location.address.split(', ')
            return ', '.join([address_parts[1], address_parts[len(address_parts) - 3], address_parts[-1]])

    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        # Handle timeout or geocoder unavailable
        print(f"Geocoding error: {str(e)}")
    except Exception as e:
        # Handle other exceptions
        print(f"Error: {str(e)}")

    return "Address not found"


class RouteRoverGui(customtkinter.CTk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.route_description = None
        self.marker_path = None
        self.marker_list = []
        self.selected_region = customtkinter.StringVar()
        self.available_regions = ["EU", "US", "IL", "AU"]
        self.fuel_values = [str(round(x / 10, 1)) for x in range(30, 101, 5)]
        self.avoid_ferries = customtkinter.BooleanVar()
        self.avoid_subscription_roads = customtkinter.BooleanVar()
        self.avoid_toll_roads = customtkinter.BooleanVar()
        self.route_calculator = RouteCalculator("Bucharest, Romania", "BRNO,Czech Republic")
        self.trip_database = TripInfoDatabase()
        self.trip_database.create_table()

        self.setup_window()
        self.create_frames()
        self.add_elements_left_frame()
        self.add_elements_right_frame()
        self.customize_elements_left_frame()
        self.customize_elements_right_frame()

        self.map_widget.set_address("Cluj Napoca")
        self.map_option_menu.set("OpenStreetMap")
        self.appearance_mode_option_menu.set("Dark")

    def create_frames(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.frame_left = customtkinter.CTkFrame(master=self, width=150, corner_radius=0, fg_color=None)
        self.frame_left.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.frame_right = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.frame_right.grid(row=0, column=1, rowspan=1, pady=0, padx=0, sticky="nsew")

    def setup_window(self):
        self.title(APP_NAME)
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.minsize(WIDTH, HEIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)
        self.createcommand("tk::mac::Quit", self.on_closing)

    def add_elements_left_frame(self):
        self.road_label = customtkinter.CTkLabel(master=self.frame_left, text="Customize your trip",
                                                 anchor="w")
        self.checkbox_ferries = customtkinter.CTkCheckBox(master=self.frame_left, text="Avoid Ferries",
                                                          command=lambda: self.avoid_ferries.set(
                                                              not self.avoid_ferries.get()), )
        self.checkbox_toll_roads = customtkinter.CTkCheckBox(master=self.frame_left, text="Avoid Toll Roads",
                                                             command=lambda: self.avoid_toll_roads.set(
                                                                 not self.avoid_toll_roads.get()), )
        self.checkbox_subscription_roads = customtkinter.CTkCheckBox(master=self.frame_left,
                                                                     text="Avoid Subscription Roads",
                                                                     command=lambda: self.avoid_subscription_roads.set(
                                                                         not self.avoid_subscription_roads.get()), )

        self.region_combobox = customtkinter.CTkComboBox(master=self.frame_left, values=self.available_regions,
                                                         width=60, command=self.on_region_selected)

        self.region_combobox.bind("<<ComboboxSelected>>", self.on_region_selected)

        self.region_label = customtkinter.CTkLabel(master=self.frame_left, text="Server Region", anchor="w")

        self.fuel_consumption_combobox = customtkinter.CTkComboBox(master=self.frame_left, values=self.fuel_values,
                                                                   width=60,
                                                                   command=self.on_fuel_consumption_selected, )
        self.fuel_consumption_combobox.bind("<<ComboboxSelected>>", self.on_fuel_consumption_selected)
        self.fuel_consumption_combobox.bind("<KeyRelease>", self.on_fuel_consumption_selected)
        self.fuel_consumption_label = customtkinter.CTkLabel(self.frame_left, text="Fuel consumption l/100 km",
                                                             anchor="w")

        self.print_text = customtkinter.CTkTextbox(self.frame_left, wrap=customtkinter.WORD, height=120, width=200)

        self.calculate_button = customtkinter.CTkButton(self.frame_left, text="Calculate",
                                                        command=self.calculate_routes, state=customtkinter.DISABLED)

        self.save_trip = customtkinter.CTkButton(self.frame_left, text="Save Trip", command=self.save_trip_database,
                                                 state=customtkinter.DISABLED)
        self.fetch_trip = customtkinter.CTkButton(self.frame_left, text="Load Trip", command=self.fetch_trip_database)
        self.map_label = customtkinter.CTkLabel(self.frame_left, text="Tile Server:", anchor="w")

        self.map_option_menu = customtkinter.CTkOptionMenu(self.frame_left, values=["OpenStreetMap", "Google normal",
                                                                                    "Google satellite"],
                                                           command=self.change_map, )

        self.appearance_mode_label = customtkinter.CTkLabel(self.frame_left, text="Appearance Mode:", anchor="w")
        self.appearance_mode_option_menu = customtkinter.CTkOptionMenu(self.frame_left,
                                                                       values=["Dark", "Light", "System"],
                                                                       command=self.change_appearance_mode)

    def add_elements_right_frame(self):

        self.frame_right.grid_rowconfigure(1, weight=1)
        self.frame_right.grid_rowconfigure(0, weight=0)
        self.frame_right.grid_columnconfigure(0, weight=1)
        self.frame_right.grid_columnconfigure(1, weight=0)

        self.map_widget = TkinterMapView(self.frame_right, corner_radius=0)
        self.entry = customtkinter.CTkEntry(master=self.frame_right, placeholder_text="type address")
        self.search_button = customtkinter.CTkButton(master=self.frame_right, text="Search", width=90,
                                                     command=self.search_event)
        self.set_marker_button = customtkinter.CTkButton(master=self.frame_right, text="Set Marker", width=90,
                                                         command=self.set_marker_event)
        self.button_2 = customtkinter.CTkButton(master=self.frame_right, text="Clear Markers",
                                                command=self.clear_marker_event, state=customtkinter.DISABLED, width=90)

    def customize_elements_right_frame(self):

        self.entry.grid(row=0, column=0, sticky="we", padx=(12, 12), pady=12)
        self.entry.bind("<Return>", lambda event=None: self.search_event())
        self.map_widget.grid(row=1, rowspan=1, column=0, columnspan=5, sticky="nswe", padx=(20, 20), pady=(20, 20))
        self.search_button.grid(row=0, column=2, sticky="w", padx=(12, 12), pady=12)
        self.set_marker_button.grid(row=0, column=3, padx=(12, 12), pady=12)
        self.button_2.grid(row=0, column=4, padx=(12, 12), pady=12)

    def customize_elements_left_frame(self):
        self.frame_left.grid_rowconfigure(4, weight=0)
        self.frame_left.grid_rowconfigure(5, weight=0)
        self.frame_left.grid_rowconfigure(6, weight=1)

        self.road_label.grid(row=0, column=0, pady=(20, 0), padx=(20, 20))
        self.checkbox_ferries.grid(row=1, column=0, padx=(20, 20), pady=(20, 0), sticky="w")
        self.checkbox_toll_roads.grid(row=2, column=0, padx=(20, 20), pady=(20, 0), sticky="w")
        self.checkbox_subscription_roads.grid(row=3, column=0, padx=(20, 20), pady=(20, 0), sticky="w")
        self.region_combobox.grid(row=4, column=0, padx=(20, 20), pady=(20, 0), sticky="e")
        self.region_label.grid(row=4, column=0, pady=(20, 0), padx=(20, 100))
        self.fuel_consumption_label.grid(row=5, column=0, pady=(20, 0), padx=(20, 100))
        self.fuel_consumption_combobox.grid(row=5, column=0, padx=(20, 20), pady=(20, 0), sticky="e")
        self.print_text.grid(row=6, column=0, padx=(10, 10), pady=(10, 10), sticky="nswe")
        self.calculate_button.grid(row=7, column=0, pady=(20, 0), padx=(20, 20))
        self.save_trip.grid(row=8, column=0, pady=(20, 0), padx=(20, 20))
        self.fetch_trip.grid(row=9, column=0, pady=(20, 0), padx=(20, 20))
        self.map_label.grid(row=10, column=0, padx=(20, 20), pady=(20, 0))
        self.map_option_menu.grid(row=11, column=0, padx=(20, 20), pady=(11, 0))
        self.appearance_mode_label.grid(row=12, column=0, padx=(20, 20), pady=(20, 0))
        self.appearance_mode_option_menu.grid(row=13, column=0, padx=(20, 20), pady=(10, 20))

    def set_marker_event(self, event=0):
        current_position = self.map_widget.get_position()
        self.marker_list.append(self.map_widget.set_marker(current_position[0], current_position[1]))

        if len(self.marker_list) >= 2:
            self.enable_button(self.calculate_button)
        else:
            self.disable_button(self.calculate_button)

        if len(self.marker_list) >= 1:
            self.enable_button(self.button_2)
        else:
            self.disable_button(self.button_2)

    def clear_marker_event(self):
        for marker in self.marker_list:
            marker.delete()
        self.marker_list.clear()
        self.disable_button(self.calculate_button)
        self.disable_button(self.button_2)
        self.connect_marker()
        self.clear_text()
        self.disable_button(self.save_trip)

    def connect_marker(self):
        position_list = []

        for marker in self.marker_list:
            position_list.append(marker.position)

        if self.marker_path is not None:
            self.map_widget.delete(self.marker_path)

        if len(position_list) > 0:
            self.marker_path = self.map_widget.set_path(position_list)

    def save_trip_database(self):
        self.trip_database.insert_trip_info(self.route_description.splitlines()[0].split(":")[1],
                                            self.route_description.splitlines()[-1].split(":")[1], self.total_time,
                                            self.total_distance, self.route_description)

        self.clear_text()
        self.print_text.insert(1.0 ,"Trip saved successfully")

    @staticmethod
    def disable_button(button: customtkinter.CTkButton):
        button.configure(state=customtkinter.DISABLED)

    @staticmethod
    def enable_button(button: customtkinter.CTkButton):
        button.configure(state=customtkinter.NORMAL)

    def calculate_routes(self):
        self.clear_text()
        self.connect_marker()
        self.total_time = 0
        self.total_distance = 0

        route_description_parts = self.calculate_route_parts()

        # Join the parts into a single string
        self.route_description = '\n'.join(route_description_parts)

        self.calculate_and_display_routes(self.route_description)
        self.enable_button(self.save_trip)

    def calculate_route_parts(self):
        route_description_parts = []

        # Add the start marker
        if len(self.marker_list) == 2:
            start_description = f"Start: {get_address_from_coordinates(self.marker_list[0])}"
            end_description = f"Destination: {get_address_from_coordinates(self.marker_list[-1])}"
            route_description_parts.extend([start_description, end_description])
        else:
            # Add the start marker
            start_description = f"Start: {get_address_from_coordinates(self.marker_list[0])}"
            route_description_parts.append(start_description)

            # Add 'Stop' for intermediate markers
            for marker in self.marker_list[1:-1]:
                stop_description = f"Stop: {get_address_from_coordinates(marker)}"
                route_description_parts.append(stop_description)

            # Add the destination marker
            end_description = f"Destination: {get_address_from_coordinates(self.marker_list[-1])}"
            route_description_parts.append(end_description)
        return route_description_parts

    def calculate_and_display_routes(self, route_description):
        for i in range(len(self.marker_list) - 1):
            start_marker = self.marker_list[i]
            end_marker = self.marker_list[i + 1]

            start_address = get_address_from_coordinates(start_marker)
            end_address = get_address_from_coordinates(end_marker)

            self.route_calculator.start_coordinates = (self.route_calculator.address_to_coordinates(start_address))
            self.route_calculator.end_coordinates = (self.route_calculator.address_to_coordinates(end_address))
            self.route_calculator.avoid_subscription_roads = self.avoid_subscription_roads.get()
            self.route_calculator.avoid_toll_roads = self.avoid_toll_roads.get()
            self.route_calculator.avoid_ferries = self.avoid_ferries.get()

            try:

                route_time, route_distance = self.route_calculator.calc_route_info()
                self.total_time += route_time
                self.total_distance += route_distance

            except RouteError as e:
                error_message = f"Error calculating route: {str(e)}"
                self.print_text.insert(customtkinter.END,
                                       f"\nError: {start_address} to {end_address}: {error_message}\n", )
        total_time_minutes = self.total_time
        hours, minutes = divmod(total_time_minutes, 60)
        formatted_time = f"{hours:.0f} hours {minutes:.0f} minutes"
        text = (
                route_description + f"\nEstimated time: {formatted_time}" + f"\nDistance: {self.total_distance:.2f} km" + f"\nFuel needed: {(self.total_distance * float(self.fuel_consumption_combobox.get())) / 100:.2f} liters")
        self.print_text.insert(index=1.0, text=text)

    def search_event(self, address=0):
        if not address:
            self.map_widget.set_address(self.entry.get())
        else:
            self.map_widget.set_address(address)

    def on_region_selected(self, event):
        self.clear_text()
        self.clear_text()
        selected_value = self.region_combobox.get()
        self.selected_region.set(selected_value)

        self.print_text.insert(index=customtkinter.END, text=f"Selected Region: {selected_value}\n")
        self.print_text.configure()

    def on_fuel_consumption_selected(self, event):

        selected_value = self.fuel_consumption_combobox.get()
        value = self.print_text.get(0.0, customtkinter.END).strip()
        if not value or "Selected" in value:
            self.clear_text()
            self.print_text.insert(index=customtkinter.END, text=f"Selected Fuel Consumption: {selected_value}\n")
        else:
            text = self.print_text.get(0.0, customtkinter.END).splitlines()
            # Replace 'your_string' with the string you want to filter
            filtered_text = [line for line in text if 'Fuel' not in line]

            # Join the filtered lines back into a single string
            resulting_text = ('\n'.join(
                filtered_text) + f"\nFuel needed: {(self.total_distance * float(self.fuel_consumption_combobox.get())) / 100:.2f} liters")
            self.clear_text()
            self.print_text.insert(0.0, resulting_text)

    def clear_text(self):
        # Delete all text from the customtkinter.CTkTextbox widget
        self.print_text.delete("1.0", "end")

    @staticmethod
    def change_appearance_mode(new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    def change_map(self, new_map: str):
        if new_map == "OpenStreetMap":
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif new_map == "Google normal":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
                                            max_zoom=22, )
        elif new_map == "Google satellite":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
                                            max_zoom=22, )

    def fetch_trip_database(self):
        trips = self.trip_database.retrieve_trip_info()
        if not trips:
            print("No trips found in the database.")
            return

        self.show_trip_selection_dialog(trips)

    def show_trip_selection_dialog(self, trips):
        # Fetch data from the database
        trips_data = self.trip_database.retrieve_trip_info()

        # Create a new Toplevel window
        self.trip_window = customtkinter.CTkToplevel(self)
        self.trip_window.title("Trip Selection")
        self.trip_window.attributes('-topmost', True)
        self.trip_window.minsize(600, 400)

        # Create a frame to contain the treeview and scrollbar
        frame = customtkinter.CTkFrame(self.trip_window)
        frame.grid(row=0, column=0, sticky="nsew")

        # Create columns and treeview
        columns = ('ID', 'Start Address', 'End Address', 'Total Time', 'Total Distance', 'Route Description')
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')

        # Add columns to the treeview
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor='center', width=100)

        # Insert data into the treeview
        for row in trips_data:
            tree.insert('', 'end', values=row)

        # Create a vertical scrollbar
        v_scrollbar = customtkinter.CTkScrollbar(frame, command=tree.yview)

        # Set the scrollbar to the treeview
        tree.configure(yscrollcommand=v_scrollbar.set)

        # Pack the components
        tree.grid(row=0, column=0, sticky="nsew")

        # Add buttons for delete and load
        delete_button = customtkinter.CTkButton(frame, text="Delete",
                                                command=lambda: self.delete_selected_trip(tree, trips_data))
        delete_button.grid(row=1, column=0, padx=20, pady=20, sticky="w")

        load_button = customtkinter.CTkButton(frame, text="Load",
                                              command=lambda: self.load_selected_trip_callback(tree, trips_data))
        load_button.grid(row=1, column=0, padx=20, pady=20, sticky="e")

        # Configure grid weights for resizing
        self.trip_window.grid_columnconfigure(0, weight=1)
        self.trip_window.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=0)

        self.trip_window.mainloop()

    def load_selected_trip_callback(self, tree, trips_data):
        selected_item = tree.selection()
        if selected_item:
            selected_index = tree.index(selected_item)
            selected_trip = trips_data[selected_index]
            self.load_selected_trip(selected_trip)

    def delete_selected_trip(self, tree, trips_data):
        selected_item = tree.selection()
        if selected_item:
            selected_index = tree.index(selected_item)
            trip_id = trips_data[selected_index][0]  # Assuming the ID is in the first column
            self.trip_database.delete_trip_info(trip_id)
            tree.delete(selected_item)

    def load_selected_trip(self, selected_trip):
        # Clear existing markers
        self.clear_marker_event()

        # Extract information from the selected trip
        start_address = selected_trip[1]
        end_address = selected_trip[2]
        route_description = selected_trip[-1]

        # Parse the route description to extract stop addresses
        stops = [line.split(":")[1] for line in route_description.split("\n") if "Stop" in line]

        route = [start_address] + stops + [end_address]

        for point in route:
            self.search_event(point)
            self.set_marker_event()
        self.connect_marker()
        self.calculate_routes()

        # Enable the save trip button
        self.enable_button(self.save_trip)
        self.trip_window.destroy()

    def on_closing(self):
        self.destroy()

    def start(self):
        self.mainloop()


if __name__ == "__main__":
    app = RouteRoverGui()
    app.start()
