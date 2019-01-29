from datetime import datetime, timedelta

from app.database.models.mentorship_relation import MentorshipRelationModel
from app.database.models.tasks_list import TasksListModel
from app.database.models.user import UserModel
from app.utils.enum_utils import MentorshipRelationState
from app import constants

class MentorshipRelationDAO:

    MAXIMUM_MENTORSHIP_DURATION = timedelta(weeks=24)  # 6 months = approximately 6*4
    MINIMUM_MENTORSHIP_DURATION = timedelta(weeks=4)

    def create_mentorship_relation(self, user_id, data):
        action_user_id = user_id
        mentor_id = data['mentor_id']
        mentee_id = data['mentee_id']
        end_date_timestamp = data['end_date']
        notes = data['notes']

        # user_id has to match either mentee_id or mentor_id
        is_valid_user_ids = action_user_id == mentor_id or action_user_id == mentee_id
        if not is_valid_user_ids:
            return constants.MATCH_EITHER_MENTOR_OR_MENTEE, 400

        # mentor_id has to be different from mentee_id
        if mentor_id == mentee_id:
            return constants.MENTOR_ID_SAME_AS_MENTEE_ID, 400

        end_date_datetime = datetime.fromtimestamp(end_date_timestamp)

        now_datetime = datetime.now()
        if end_date_datetime < now_datetime:
            return constants.END_TIME_BEFORE_PRESENT, 400

        # business logic constraints

        max_relation_duration = end_date_datetime - now_datetime
        if max_relation_duration > self.MAXIMUM_MENTORSHIP_DURATION:
            return constants.MENTOR_TIME_GREATER_THAN_MAX_TIME, 400

        if max_relation_duration < self.MINIMUM_MENTORSHIP_DURATION:
            return constants.MENTOR_TIME_LESS_THAN_MIN_TIME, 400

        # validate if mentor user exists
        mentor_user = UserModel.find_by_id(mentor_id)
        if mentor_user is None:
            return constants.MENTOR_DOES_NOT_EXIST, 404

        # validate if mentor is available to mentor
        if not mentor_user.available_to_mentor:
            return constants.MENTOR_NOT_AVAILABLE_TO_MENTOR, 400

        # validate if mentee user exists
        mentee_user = UserModel.find_by_id(mentee_id)
        if mentee_user is None:
            return constants.MENTEE_DOES_NOT_EXIST, 404

        # validate if mentee is wants to be mentored
        if not mentee_user.need_mentoring:
            return constants.MENTEE_NOT_AVAIL_TOBE_MENTORED, 400


        # TODO add tests for this portion

        all_mentor_relations = mentor_user.mentor_relations + mentor_user.mentee_relations
        for relation in all_mentor_relations:
            if relation.state is MentorshipRelationState.ACCEPTED:
                return constants.MENTOR_IN_RELATION, 400

        all_mentee_relations = mentee_user.mentor_relations + mentee_user.mentee_relations
        for relation in all_mentee_relations:
            if relation.state is MentorshipRelationState.ACCEPTED:
                return constants.MENTEE_ALREADY_IN_A_RELATION, 400

        # All validations were checked

        tasks_list = TasksListModel()
        tasks_list.save_to_db()

        mentorship_relation = MentorshipRelationModel(action_user_id=action_user_id,
                                                      mentor_user=mentor_user,
                                                      mentee_user=mentee_user,
                                                      creation_date=datetime.now().timestamp(),
                                                      end_date=end_date_timestamp,
                                                      state=MentorshipRelationState.PENDING,
                                                      notes=notes,
                                                      tasks_list=tasks_list)

        mentorship_relation.save_to_db()

        return constants.MENTORSHIP_RELATION_WAS_SENT_SUCCESSFULLY, 200

    @staticmethod
    def list_mentorship_relations(user_id=None, accepted=None, pending=None, completed=None, cancelled=None, rejected=None):
        if pending is not None:
            return constants.NOT_IMPLEMENTED, 200
        if completed is not None:
            return constants.NOT_IMPLEMENTED, 200
        if cancelled is not None:
            return constants.NOT_IMPLEMENTED, 200
        if accepted is not None:
            return constants.NOT_IMPLEMENTED, 200
        if rejected is not None:
            return constants.NOT_IMPLEMENTED, 200

        user = UserModel.find_by_id(user_id)

        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        all_relations = user.mentor_relations + user.mentee_relations

        # add extra field for api response
        for relation in all_relations:
            setattr(relation, 'sent_by_me', relation.action_user_id == user_id)

        return all_relations, 200

    @staticmethod
    def accept_request(user_id, request_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        request = MentorshipRelationModel.find_by_id(request_id)

        # verify if request exists
        if request is None:
            return constants.MENTORSHIP_RELATION_REQUEST_DOES_NOT_EXIST, 404

        # verify if request is in pending state
        if request.state is not MentorshipRelationState.PENDING:
            return constants.NOT_PENDING_STATE_RELATION, 400

        # verify if I'm the receiver of the request
        if request.action_user_id is user_id:
            return constants.CANT_ACCEPT_MENTOR_REQ_SENT_BY_USER, 400

        # verify if I'm involved in this relation
        if not (request.mentee_id is user_id or request.mentor_id is user_id):
            return constants.CANT_ACCEPT_UNINVOLVED_MENTOR_RELATION, 400

        requests = user.mentee_relations + user.mentor_relations

        # verify if I'm on a current relation
        for request in requests:
            if request.state is MentorshipRelationState.ACCEPTED:
                return constants.USER_IS_INVOLVED_IN_A_MENTORSHIP_RELATION, 400

        # All was checked
        request.state = MentorshipRelationState.ACCEPTED
        request.save_to_db()

        return constants.MENTORSHIP_RELATION_WAS_ACCEPTED_SUCCESSFULLY, 200

    @staticmethod
    def reject_request(user_id, request_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        request = MentorshipRelationModel.find_by_id(request_id)

        # verify if request exists
        if request is None:
            return constants.MENTORSHIP_RELATION_REQUEST_DOES_NOT_EXIST, 404

        # verify if request is in pending state
        if request.state is not MentorshipRelationState.PENDING:
            return constants.NOT_PENDING_STATE_RELATION, 400

        # verify if I'm the receiver of the request
        if request.action_user_id is user_id:
            return constants.USER_CANT_REJECT_REQUEST_FOR_MENTOR, 400

        # verify if I'm involved in this relation
        if not (request.mentee_id is user_id or request.mentor_id is user_id):
            return constants.CANT_REJECT_UNINVOLVED_RELATION_REQUEST, 400

        # All was checked
        request.state = MentorshipRelationState.REJECTED
        request.save_to_db()

        return constants.MENTORSHIP_RELATION_WAS_REJECTED_SUCCESSFULLY, 200

    @staticmethod
    def cancel_relation(user_id, relation_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        request = MentorshipRelationModel.find_by_id(relation_id)

        # verify if request exists
        if request is None:
            return constants.MENTORSHIP_RELATION_REQUEST_DOES_NOT_EXIST, 404

        # verify if request is in pending state
        if request.state is not MentorshipRelationState.ACCEPTED:
            return constants.UNACCEPTED_STATE_RELATION, 400

        # verify if I'm involved in this relation
        if not (request.mentee_id is user_id or request.mentor_id is user_id):
            return constants.CANT_CANCEL_UNINVOLVED_REQUEST, 400

        # All was checked
        request.state = MentorshipRelationState.CANCELLED
        request.save_to_db()

        return constants.MENTORSHIP_RELATION_WAS_CANCELLED_SUCCESSFULLY, 200

    @staticmethod
    def delete_request(user_id, request_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        request = MentorshipRelationModel.find_by_id(request_id)

        # verify if request exists
        if request is None:
            return constants.MENTORSHIP_RELATION_REQUEST_DOES_NOT_EXIST, 404

        # verify if request is in pending state
        if request.state is not MentorshipRelationState.PENDING:
            return constants.NOT_PENDING_STATE_RELATION, 400

        # verify if user created the mentorship request
        if request.action_user_id is not user_id:
            return constants.CANT_DELETE_UNINVOLVED_REQUEST, 400

        # All was checked
        request.delete_from_db()

        return constants.MENTORSHIP_RELATION_WAS_DELETED_SUCCESSFULLY, 200

    @staticmethod
    def list_past_mentorship_relations(user_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        now_timestamp = datetime.now().timestamp()
        past_relations = []
        all_relations = user.mentor_relations + user.mentee_relations

        for relation in all_relations:
            if relation.end_date < now_timestamp:
                setattr(relation, 'sent_by_me', relation.action_user_id == user_id)
                past_relations += [relation]

        return past_relations, 200

    @staticmethod
    def list_current_mentorship_relation(user_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        all_relations = user.mentor_relations + user.mentee_relations

        for relation in all_relations:
            if relation.state is MentorshipRelationState.ACCEPTED:
                setattr(relation, 'sent_by_me', relation.action_user_id == user_id)
                return relation

        return constants.NOT_IN_MENTORED_RELATION_CURRENTLY, 200

    @staticmethod
    def list_pending_mentorship_relations(user_id):

        user = UserModel.find_by_id(user_id)

        # verify if user exists
        if user is None:
            return constants.USER_DOES_NOT_EXIST, 404

        now_timestamp = datetime.now().timestamp()
        pending_requests = []
        all_relations = user.mentor_relations + user.mentee_relations

        for relation in all_relations:
            if relation.state is MentorshipRelationState.PENDING and relation.end_date > now_timestamp:
                setattr(relation, 'sent_by_me', relation.action_user_id == user_id)
                pending_requests += [relation]

        return pending_requests, 200
