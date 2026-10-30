from sqlalchemy import select, text
from backend.app.db.models import Appointment, EmergencyCase, Hospital, HospitalConnection
from backend.app.structures.queue import Queue
from backend.app.structures.priority_queue import PriorityQueue
from backend.app.structures.graph import Graph
from backend.app.services.access import permitted_patient_ids


def hospital_lock(db, hospital_id, module):
    # Separate 32-bit key spaces: 1 appointments, 2 emergencies, 3 referrals.
    db.execute(text('SELECT pg_advisory_xact_lock(:module, :hospital)'),
               {'module': module, 'hospital': hospital_id})


def waiting_queue(db, hospital_id):
    queue = Queue()
    rows = db.scalars(select(Appointment).where(Appointment.hospital_id == hospital_id,
                      Appointment.status == 'waiting',
                      Appointment.patient_id.in_(permitted_patient_ids(hospital_id)))
                      .order_by(Appointment.checked_in_at, Appointment.id))
    for row in rows:
        queue.enqueue(row)
    return queue


def emergency_heap(db, hospital_id):
    heap = PriorityQueue()
    for row in db.scalars(select(EmergencyCase).where(EmergencyCase.hospital_id == hospital_id,
                                                     EmergencyCase.status == 'waiting',
                                                     EmergencyCase.patient_id.in_(permitted_patient_ids(hospital_id)))):
        heap.insert(row.id, row.priority, row.arrived_at, row)
    return heap


def hospital_graph(db):
    graph = Graph()
    for hospital in db.scalars(select(Hospital).order_by(Hospital.id)):
        graph.add_node(hospital.id)
    for edge in db.scalars(select(HospitalConnection).order_by(HospitalConnection.source_id,
                                                             HospitalConnection.destination_id)):
        graph.add_edge(edge.source_id, edge.destination_id)
    return graph
