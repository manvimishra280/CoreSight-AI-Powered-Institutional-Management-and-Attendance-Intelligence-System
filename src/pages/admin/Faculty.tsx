import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';

import {
  assignFacultyBatches,
  fetchBatches,
  fetchFacultyList,
} from '../../api/batches';

import {
  getFacultyRegistrationRequests,
  type FacultyRegistrationAdminRequest,
} from '../../api/faculty';

import type { Batch, FacultyRecord } from '../../types';


export default function Faculty() {

  // ============================================================
  // DATA
  // ============================================================

  const [facultyList, setFacultyList] = useState<FacultyRecord[]>([]);

  const [batches, setBatches] = useState<Batch[]>([]);

  const [requests, setRequests] = useState<
    FacultyRegistrationAdminRequest[]
  >([]);

  const [loadingRequests, setLoadingRequests] = useState(true);

  const [requestError, setRequestError] = useState('');


  // ============================================================
  // FACULTY ASSIGNMENT MODAL STATE
  // ============================================================

  const [selectedFaculty, setSelectedFaculty] =
    useState<FacultyRecord | null>(null);

  const [selectedBatchIds, setSelectedBatchIds] =
    useState<string[]>([]);

  const [savingAssignment, setSavingAssignment] =
    useState(false);

  const [assignmentError, setAssignmentError] =
    useState('');


  // ============================================================
  // LOAD DATA
  // ============================================================

  useEffect(() => {

    async function loadData() {

      try {

        const [facultyData, batchData] = await Promise.all([
          fetchFacultyList(),
          fetchBatches(),
        ]);

        setFacultyList(facultyData);

        setBatches(batchData);

      } catch (err) {

        console.error('Unable to load faculty data', err);

      }

    }


    async function loadRequests() {

      try {

        setRequestError('');

        const data =
          await getFacultyRegistrationRequests();

        setRequests(data);

      } catch (err) {

        setRequestError(
          err instanceof Error
            ? err.message
            : 'Unable to load registration requests.'
        );

      } finally {

        setLoadingRequests(false);

      }

    }


    loadData();

    loadRequests();

  }, []);


  // ============================================================
  // HELPERS
  // ============================================================


  function openAssignment(faculty: FacultyRecord) {

    setSelectedFaculty(faculty);

    // Pre-select currently assigned batches
    setSelectedBatchIds(
      faculty.assignedBatchIds
    );

    setAssignmentError('');

  }


  function closeAssignment() {

    setSelectedFaculty(null);

    setSelectedBatchIds([]);

    setAssignmentError('');

  }


  function toggleBatch(batchId: string) {

    setSelectedBatchIds((current) => {

      if (current.includes(batchId)) {

        return current.filter(
          (id) => id !== batchId
        );

      }

      return [...current, batchId];

    });

  }


  // ============================================================
  // SAVE ASSIGNMENT
  // ============================================================

  async function saveAssignment() {

    if (!selectedFaculty) {
      return;
    }


    try {

      setSavingAssignment(true);

      setAssignmentError('');


      const updatedFaculty =
        await assignFacultyBatches(
          selectedFaculty.id,
          selectedBatchIds
        );


      // Update faculty list immediately
      setFacultyList((current) =>
        current.map((faculty) =>
          faculty.id === updatedFaculty.id
            ? updatedFaculty
            : faculty
        )
      );


      closeAssignment();

    } catch (err) {

      setAssignmentError(
        err instanceof Error
          ? err.message
          : 'Unable to assign batches.'
      );

    } finally {

      setSavingAssignment(false);

    }

  }


  // ============================================================
  // REGISTRATION REQUESTS
  // ============================================================

  const pendingRequests = requests.filter(
    (request) =>
      request.status === 'PENDING'
  );


  return (

    <AppLayout
      role="admin"
      title="Faculty"
    >


      {/* ===================================================== */}
      {/* REGISTRATION REQUESTS */}
      {/* ===================================================== */}

      <section className="mb-8">

        <div className="flex items-center justify-between mb-4">

          <div>

            <h2 className="font-display text-base font-semibold">

              Registration Requests

            </h2>

            <p className="text-xs text-text-dim mt-1">

              Faculty access requests awaiting review.

            </p>

          </div>


          {pendingRequests.length > 0 && (

            <span className="px-2.5 py-1 rounded-full bg-accent/10 text-accent text-xs font-medium">

              {pendingRequests.length} pending

            </span>

          )}

        </div>


        {loadingRequests && (

          <Card className="p-4">

            <p className="text-sm text-text-dim">

              Loading requests…

            </p>

          </Card>

        )}


        {!loadingRequests &&
          requestError && (

            <Card className="p-4">

              <p className="text-sm text-blocked">

                {requestError}

              </p>

            </Card>

          )}


        {!loadingRequests &&
          !requestError &&
          pendingRequests.length === 0 && (

            <Card className="p-4">

              <p className="text-sm text-text-dim">

                No pending faculty registration requests.

              </p>

            </Card>

          )}


        {!loadingRequests &&
          !requestError &&
          pendingRequests.length > 0 && (

            <div className="space-y-2">

              {pendingRequests.map(
                (request) => (

                  <Card
                    key={request.id}
                    className="px-4 py-3"
                  >

                    <div className="flex items-center gap-4">


                      {/* NAME */}

                      <div className="min-w-0 flex-1">

                        <p className="font-display text-sm font-semibold truncate">

                          {request.full_name}

                        </p>

                      </div>


                      {/* FACULTY ID */}

                      <div className="hidden sm:block w-24">

                        <p className="text-xs text-text-dim">

                          {request.employee_id}

                        </p>

                      </div>


                      {/* DEPARTMENT */}

                      <div className="hidden md:block w-32">

                        <p className="text-xs text-text-dim truncate">

                          {request.department_code}

                        </p>

                      </div>


                      {/* STATUS */}

                      <div className="w-20">

                        <span className="inline-flex px-2 py-1 rounded-full bg-accent/10 text-accent text-[10px] font-medium uppercase tracking-wider">

                          Pending

                        </span>

                      </div>


                      {/* VIEW */}

                      <Link
                        to={`/admin/faculty/requests/${request.id}`}
                        className="text-xs text-accent hover:underline shrink-0"
                      >

                        View

                      </Link>


                    </div>

                  </Card>

                )
              )}

            </div>

          )}

      </section>



      {/* ===================================================== */}
      {/* EXISTING FACULTY */}
      {/* ===================================================== */}

      <section>


        <div className="flex items-center justify-between mb-4">

          <div>

            <h2 className="font-display text-base font-semibold">

              Faculty

            </h2>

            <p className="text-xs text-text-dim mt-1">

              Faculty members currently registered in CoreSight.

            </p>

          </div>

        </div>



        {facultyList.length === 0 ? (

          <Card className="p-5">

            <p className="text-sm text-text-dim">

              No faculty members registered yet.

            </p>

          </Card>

        ) : (

          <div className="grid sm:grid-cols-2 gap-3">

            {facultyList.map((faculty) => (

              <Card
                key={faculty.id}
                className="p-4"
              >


                {/* FACULTY INFO */}

                <div className="flex items-start justify-between gap-3">

                  <div className="min-w-0">

                    <p className="font-display text-sm font-semibold">

                      {faculty.name}

                    </p>

                    <p className="text-xs text-text-dim mt-0.5">

                      {faculty.email}

                    </p>

                  </div>


                  {/* ASSIGN BUTTON */}

                  <button
                    type="button"
                    onClick={() =>
                      openAssignment(faculty)
                    }
                    className="shrink-0 px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 transition"
                  >

                    Assign Batches

                  </button>

                </div>



                {/* ASSIGNED BATCHES */}

                <div className="mt-4">

                  <p className="text-xs text-text-faint uppercase tracking-wider">

                    Assigned batches

                  </p>


                  {faculty.assignedBatchIds.length === 0 ? (

                    <p className="text-sm text-text-dim mt-1">

                      No batches assigned

                    </p>

                  ) : (

                    <div className="flex flex-wrap gap-2 mt-2">

                      {faculty.assignedBatchIds.map(
                        (batchId) => {

                          const batch =
                            batches.find(
                              (item) =>
                                item.id === batchId
                            );


                          return (

                            <span
                              key={batchId}
                              className="px-2 py-1 rounded-md bg-accent/10 text-accent text-xs"
                            >

                              {batch?.name ?? batchId}

                            </span>

                          );

                        }
                      )}

                    </div>

                  )}

                </div>


              </Card>

            ))}

          </div>

        )}

      </section>



      {/* ===================================================== */}
      {/* ASSIGN BATCHES MODAL */}
      {/* ===================================================== */}

      {selectedFaculty && (

        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">


          {/* BACKDROP */}

          <div
            className="absolute inset-0 bg-black/60"
            onClick={closeAssignment}
          />


          {/* MODAL */}

          <div className="relative z-10 w-full max-w-lg max-h-[85vh] overflow-hidden rounded-2xl bg-surface border border-white/10 shadow-2xl">


            {/* HEADER */}

            <div className="p-5 border-b border-white/10">

              <div className="flex items-start justify-between gap-4">

                <div>

                  <h2 className="font-display text-lg font-semibold">

                    Assign Batches

                  </h2>

                  <p className="text-sm text-text-dim mt-1">

                    Select the batches assigned to

                    {' '}

                    <span className="font-medium text-text">

                      {selectedFaculty.name}

                    </span>

                  </p>

                </div>


                <button
                  type="button"
                  onClick={closeAssignment}
                  className="text-text-dim hover:text-text text-xl"
                >

                  ×

                </button>

              </div>

            </div>



            {/* BATCH LIST */}

            <div className="p-5 overflow-y-auto max-h-[50vh]">


              {batches.length === 0 ? (

                <p className="text-sm text-text-dim">

                  No batches available.

                </p>

              ) : (

                <div className="space-y-2">

                  {batches.map((batch) => (

                    <label
                      key={batch.id}
                      className="flex items-center gap-3 p-3 rounded-xl border border-white/10 cursor-pointer hover:bg-white/5 transition"
                    >

                      <input
                        type="checkbox"
                        checked={selectedBatchIds.includes(
                          batch.id
                        )}
                        onChange={() =>
                          toggleBatch(batch.id)
                        }
                        className="h-4 w-4"
                      />


                      <div className="min-w-0">

                        <p className="text-sm font-medium">

                          {batch.name}

                        </p>


                        <p className="text-xs text-text-dim mt-0.5">

                          {batch.department}

                          {' • '}

                          Year {batch.year}

                          {' • '}

                          Section {batch.section}

                        </p>

                      </div>

                    </label>

                  ))}

                </div>

              )}


              {/* ERROR */}

              {assignmentError && (

                <div className="mt-4 p-3 rounded-lg bg-blocked/10">

                  <p className="text-sm text-blocked">

                    {assignmentError}

                  </p>

                </div>

              )}

            </div>



            {/* FOOTER */}

            <div className="p-5 border-t border-white/10 flex justify-end gap-3">


              <button
                type="button"
                onClick={closeAssignment}
                disabled={savingAssignment}
                className="px-4 py-2 rounded-lg border border-white/10 text-sm text-text-dim hover:text-text transition disabled:opacity-50"
              >

                Cancel

              </button>


              <button
                type="button"
                onClick={saveAssignment}
                disabled={savingAssignment}
                className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
              >

                {savingAssignment
                  ? 'Saving…'
                  : 'Save Assignment'}

              </button>


            </div>


          </div>

        </div>

      )}


    </AppLayout>

  );

}