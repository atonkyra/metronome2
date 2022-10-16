import time
import socket
import json
import threading
import argparse
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY


parser = argparse.ArgumentParser(description='metronome clocktower')
parser.add_argument('-b', '--bind-address', required=False, help='bind address for clocktower messages', default='0.0.0.0')
parser.add_argument('-p', '--bind-port', required=False, help='bind port for clocktower messages', default='4444', type=int)
parser.add_argument('-e', '--exporter-port', required=False, help='bind port for prometheus exporter', default='8415', type=int)
parser.add_argument('-d', '--debug', required=False, action='store_true', default=False)
args = parser.parse_args()


SESSION_TIMEOUT = 10.0

hub_sessions = {}
hub_sessions_lock = threading.Lock()
client_sessions = {}
client_sessions_lock = threading.Lock()
msglistener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
msglistener.bind((args.bind_address, args.bind_port))


class CustomCollector(object):
    def collect(self):
        global hub_sessions
        global hub_sessions_lock
        global client_sessions
        global client_sessions_lock

        hub_received_messages = CounterMetricFamily(
            'metronome2_hub_received_messages',
            'Messages received by the metronome hub',
            labels=['sid']
        )
        hub_holes_created = CounterMetricFamily(
            'metronome2_hub_holes_created',
            'Holes created within session',
            labels=['sid']
        )
        hub_holes_closed = CounterMetricFamily(
            'metronome2_hub_holes_closed',
            'Holes closed within session',
            labels=['sid']
        )
        hub_holes_timed_out = CounterMetricFamily(
            'metronome2_hub_holes_timed_out',
            'Holes timed out within session',
            labels=['sid']
        )
        hub_holes_current = GaugeMetricFamily(
            'metronome2_hub_holes_current',
            'Current holes within session',
            labels=['sid']
        )
        hub_payload_bytes = CounterMetricFamily(
            'metronome2_hub_received_bytes',
            'Payload bytes received by the hub',
            labels=['sid']
        )
        hub_intermessage_gap_mavg_seconds = GaugeMetricFamily(
            'metronome2_hub_intermessage_gap_mavg',
            'Moving average of intermessage gap',
            labels=['sid']
        )
        hub_receive_time_window_messages = GaugeMetricFamily(
            'metronome2_hub_receive_time_window_messages',
            'Messages received by time window',
            labels=['sid', 'window']
        )

        client_unexpected_increments = CounterMetricFamily(
            'metronome2_client_seq_unexpected_increment',
            'Unexpected sequence number increments',
            labels=['sid']
        )
        client_unexpected_decrements = CounterMetricFamily(
            'metronome2_client_seq_unexpected_decrement',
            'Unexpected sequence number decrements',
            labels=['sid']
        )
        client_sent_messages = CounterMetricFamily(
            'metronome2_client_sent_messages',
            'Messages sent by the metronome client',
            labels=['sid']
        )
        client_received_messages = CounterMetricFamily(
            'metronome2_client_received_messages',
            'Messages received by the metronome client',
            labels=['sid']
        )
        client_timely_received_messages = CounterMetricFamily(
            'metronome2_client_timely_received_messages',
            'Timely messages received by the metronome client',
            labels=['sid']
        )
        client_lost_messages = CounterMetricFamily(
            'metronome2_client_lost_messages',
            'Messages lost',
            labels=['sid']
        )
        client_inflight_messages = GaugeMetricFamily(
            'metronome2_client_inflight_messages',
            'Current messages in-flight',
            labels=['sid']
        )
        client_rtt_worst_seconds = GaugeMetricFamily(
            'metronome2_client_rtt_worst',
            'Worst RTT seen by client',
            labels=['sid']
        )
        client_rtt_best_seconds = GaugeMetricFamily(
            'metronome2_client_rtt_best',
            'Best RTT seen by client',
            labels=['sid']
        )
        client_rtt_mavg_seconds = GaugeMetricFamily(
            'metronome2_client_rtt_mavg',
            'Moving average of RTT',
            labels=['sid']
        )
        client_payload_bytes = CounterMetricFamily(
            'metronome2_client_received_bytes',
            'Payload bytes received by the client',
            labels=['sid']
        )
        client_intermessage_gap_mavg_seconds = GaugeMetricFamily(
            'metronome2_client_intermessage_gap_mavg',
            'Moving average of intermessage gap',
            labels=['sid']
        )
        client_receive_time_window_messages = GaugeMetricFamily(
            'metronome2_client_receive_time_window_messages',
            'Messages received by time window',
            labels=['sid', 'window']
        )

        with hub_sessions_lock:
            for sid, session_info in hub_sessions.items():
                hub_received_messages.add_metric(
                    [sid], session_info.get('received_messages'), timestamp=session_info.get('timestamp')
                )
                hub_holes_created.add_metric(
                    [sid], session_info.get('holes_created'), timestamp=session_info.get('timestamp')
                )
                hub_holes_closed.add_metric(
                    [sid], session_info.get('holes_closed'), timestamp=session_info.get('timestamp')
                )
                hub_holes_timed_out.add_metric(
                    [sid], session_info.get('holes_timed_out'), timestamp=session_info.get('timestamp')
                )
                hub_holes_current.add_metric(
                    [sid], session_info.get('holes_current'), timestamp=session_info.get('timestamp')
                )
                hub_payload_bytes.add_metric(
                    [sid], session_info.get('received_bytes'), timestamp=session_info.get('timestamp')
                )
                if session_info.get('intermessage_gap_mavg') is not None:
                    hub_intermessage_gap_mavg_seconds.add_metric(
                        [sid], session_info.get('intermessage_gap_mavg'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('receive_time_windows') is not None:
                    i = 0
                    for window in session_info.get('receive_time_windows'):
                        hub_receive_time_window_messages.add_metric(
                            [sid, str(i)],
                            window, timestamp=session_info.get('timestamp')
                        )
                        i += 1

        with client_sessions_lock:
            for sid, session_info in client_sessions.items():
                client_unexpected_increments.add_metric(
                    [sid], session_info.get('seq_unexpected_increment'), timestamp=session_info.get('timestamp')
                )
                client_unexpected_decrements.add_metric(
                    [sid], session_info.get('seq_unexpected_decrement'), timestamp=session_info.get('timestamp')
                )
                client_sent_messages.add_metric(
                    [sid], session_info.get('sent_messages'), timestamp=session_info.get('timestamp')
                )
                client_received_messages.add_metric(
                    [sid], session_info.get('received_messages'), timestamp=session_info.get('timestamp')
                )
                client_timely_received_messages.add_metric(
                    [sid], session_info.get('timely_received_messages'), timestamp=session_info.get('timestamp')
                )
                client_lost_messages.add_metric(
                    [sid], session_info.get('lost_messages'), timestamp=session_info.get('timestamp')
                )
                client_inflight_messages.add_metric(
                    [sid], session_info.get('inflight_messages'), timestamp=session_info.get('timestamp')
                )
                if session_info.get('rtt_worst') is not None:
                    client_rtt_worst_seconds.add_metric(
                        [sid], session_info.get('rtt_worst'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('rtt_best') is not None:
                    client_rtt_best_seconds.add_metric(
                        [sid], session_info.get('rtt_best'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('rtt_mavg') is not None:
                    client_rtt_mavg_seconds.add_metric(
                        [sid], session_info.get('rtt_mavg'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('received_bytes') is not None:
                    client_payload_bytes.add_metric(
                        [sid], session_info.get('received_bytes'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('intermessage_gap_mavg') is not None:
                    client_intermessage_gap_mavg_seconds.add_metric(
                        [sid], session_info.get('intermessage_gap_mavg'), timestamp=session_info.get('timestamp')
                    )
                if session_info.get('receive_time_windows') is not None:
                    i = 0
                    for window in session_info.get('receive_time_windows'):
                        client_receive_time_window_messages.add_metric(
                            [sid, str(i)],
                            window, timestamp=session_info.get('timestamp')
                        )
                        i += 1

        yield hub_received_messages
        yield hub_holes_created
        yield hub_holes_closed
        yield hub_holes_timed_out
        yield hub_holes_current
        yield hub_payload_bytes
        yield hub_intermessage_gap_mavg_seconds
        yield hub_receive_time_window_messages

        yield client_unexpected_increments
        yield client_unexpected_decrements
        yield client_sent_messages
        yield client_received_messages
        yield client_timely_received_messages
        yield client_lost_messages
        yield client_inflight_messages
        yield client_rtt_worst_seconds
        yield client_rtt_best_seconds
        yield client_rtt_mavg_seconds
        yield client_payload_bytes
        yield client_intermessage_gap_mavg_seconds
        yield client_receive_time_window_messages


def inject_client_session_statistics(payload):
    global client_sessions
    global client_sessions_lock
    sid = payload.get('sid')
    with client_sessions_lock:
        if args.debug:
            print(json.dumps(payload))
        client_sessions[sid] = payload


def inject_hub_session_statistics(payload):
    global hub_sessions
    global hub_sessions_lock
    sid = payload.get('sid')
    with hub_sessions_lock:
        if args.debug:
            print(json.dumps(payload))
        hub_sessions[sid] = payload


def cleanup_sessions():
    global hub_sessions
    global hub_sessions_lock
    global client_sessions
    global client_sessions_lock

    while True:
        current_time = time.time()
        with client_sessions_lock:
            remove_list = []
            for sid, session in client_sessions.items():
                age = current_time - session.get('timestamp')
                if age > SESSION_TIMEOUT:
                    remove_list.append(sid)
            for sid in remove_list:
                del client_sessions[sid]
        with hub_sessions_lock:
            remove_list = []
            for sid, session in hub_sessions.items():
                age = current_time - session.get('timestamp')
                if age > SESSION_TIMEOUT:
                    remove_list.append(sid)
            for sid in remove_list:
                del hub_sessions[sid]
        time.sleep(1)


def main():
    threading.Thread(target=cleanup_sessions, daemon=True).start()
    REGISTRY.register(CustomCollector())
    start_http_server(args.exporter_port)
    while True:
        try:
            payload = json.loads(msglistener.recv(4096).decode('ascii', errors='ignore'))
            if payload.get('clocktower_type') == 'hub_session_statistics':
                inject_hub_session_statistics(payload)
            if payload.get('clocktower_type') == 'client_session_statistics':
                inject_client_session_statistics(payload)
        except json.decoder.JSONDecodeError:
            pass


if __name__ == '__main__':
    main()

