import paho.mqtt.client as mqtt
import stmpy
import logging
import json

# TODO: choose proper MQTT broker address
MQTT_BROKER = '127.0.0.1'
MQTT_PORT = 1883

# TODO: choose proper topics for communication
MQTT_TOPIC_INPUT = 'team5/commands'
MQTT_TOPIC_OUTPUT = 'team5/status'


class TimerLogic:
    """
    State Machine for a named timer.

    This is the support object for a state machine that models a single timer.
    """

    def __init__(self, name, duration, component):
        self._logger = logging.getLogger(__name__)
        self.name = name
        self.duration = duration
        self.component = component

        t0 = {
            'source': 'initial',
            'target': 'active',
            'effect': 'start_timer("t", ' + str(self.duration * 1000) + ")'"
        }

        t1 = {
            'trigger': 'report',
            'source': 'active',
            'target': 'active',
            'effect': 'report_status'
        }

        t2 = {
            'trigger': 't',
            'source': 'active',
            'target': 'finished',
            'effect': 'timer_finished'
        }

        self.stm = stmpy.Machine(name=name, transitions=[t0, t1, t2], obj=self)

    def timer_finished(self):
        self.component.timer_finished(self.name)

    def report_status(self):
        time_rem = self.stm.get_timer('t')
        self.component.report_status(self.name, time_rem)



class TimerManagerComponent:
    """
    The component to manage named timers in a voice assistant.

    This component connects to an MQTT broker and listens to commands.
    To interact with the component, do the following:

    * Connect to the same broker as the component. You find the broker address
    in the value of the variable `MQTT_BROKER`.
    * Subscribe to the topic in variable `MQTT_TOPIC_OUTPUT`. On this topic, the
    component sends its answers.
    * Send the messages listed below to the topic in variable `MQTT_TOPIC_INPUT`.

        {"command": "new_timer", "name": "spaghetti", "duration":50}

        {"command": "status_all_timers"}

        {"command": "status_single_timer", "name": "spaghetti"}

    """

    def on_connect(self, client, userdata, flags, rc):
        # we just log that we are connected
        print("Connected")
        self._logger.debug('MQTT connected to {}'.format(client))

    def on_message(self, client, userdata, msg):
        print("Fått melding")
        """
        Processes incoming MQTT messages.

        We assume the payload of all received MQTT messages is an UTF-8 encoded
        string, which is formatted as a JSON object. The JSON object contains
        a field called `command` which identifies what the message should achieve.

        As a reaction to a received message, we can for example do the following:

        * create a new state machine instance to handle the incoming messages,
        * route the message to an existing state machine session,
        * handle the message right here,
        * throw the message away.

        """
        self._logger.debug('Incoming message to topic {}'.format(msg.topic))

        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as err:
            self._logger.error('Message sent to topic {} had no valid JSON. Message ignored. {}'.format(msg.topic, err))
            return

        name = payload.get('name')
        duration = payload.get('duration')
        command = payload.get('command')

        print(name)
        print(command)

        if command == "new_timer":
            tl = TimerLogic(name, duration, self)
            self.stm_driver.add_machine(tl.stm)
            self.machines.append(name)
        elif command == "status_all_timers":
            for machine_id in self.machines:
                self.stm_driver.send("report", machine_id)
        elif command == "status_single_timer":
            self.stm_driver.send("report", name)

    def report_status(self, name, time_rem):
        output = "Status: Time left for {}: {} seconds".format(name, str(time_rem / 1000))
        print(output)
        self.mqtt_client.publish(MQTT_TOPIC_OUTPUT, output)

    def timer_finished(self, name):
        output = "timer {} finished".format(name)
        print(output)
        self.mqtt_client.publish(MQTT_TOPIC_OUTPUT, output)

    def __init__(self):
        """
        Start the component.

        ## Start of MQTT
        We subscribe to the topic(s) the component listens to.
        The client is available as variable `self.client` so that subscriptions
        may also be changed over time if necessary.

        The MQTT client reconnects in case of failures.

        ## State Machine driver
        We create a single state machine driver for STMPY. This should fit
        for most components. The driver is available from the variable
        `self.driver`. You can use it to send signals into specific state
        machines, for instance.

        """
        # get the logger object for the component
        self._logger = logging.getLogger(__name__)
        print('logging under name {}.'.format(__name__))
        self._logger.info('Starting Component')

        # create a new MQTT client
        self._logger.debug('Connecting to MQTT broker {} at port {}'.format(MQTT_BROKER, MQTT_PORT))
        self.mqtt_client = mqtt.Client()
        # callback methods
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        # Connect to the broker
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        # subscribe to proper topic(s) of your choice
        self.mqtt_client.subscribe(MQTT_TOPIC_INPUT)
        # start the internal loop to process MQTT messages
        self.mqtt_client.loop_start()

        # we start the stmpy driver, without any state machines for now
        self.stm_driver = stmpy.Driver()
        self.stm_driver.start(keep_active=True)
        self._logger.debug('Component initialization finished')
        self.machines = []

    def stop(self):
        """
        Stop the component.
        """
        # stop the MQTT client
        self.mqtt_client.loop_stop()

        # stop the state machine Driver
        self.stm_driver.stop()


# logging.DEBUG: Most fine-grained logging, printing everything
# logging.INFO:  Only the most important informational log items
# logging.WARN:  Show only warnings and errors.
# logging.ERROR: Show only error messages.
debug_level = logging.DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(debug_level)
ch = logging.StreamHandler()
ch.setLevel(debug_level)
formatter = logging.Formatter('%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

t = TimerManagerComponent()
