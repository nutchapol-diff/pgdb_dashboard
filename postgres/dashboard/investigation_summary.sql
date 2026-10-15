SELECT COALESCE(sum(f.exam_records),0)::bigint AS exam_records,
       COALESCE(sum(f.detail_service_exams),0)::bigint AS detail_service_exams,
       COALESCE(sum(f.definition_service_exams),0)::bigint AS definition_service_exams,
       COALESCE(sum(f.captured_exams),0)::bigint AS captured_exams,
       COALESCE(sum(f.suspected_uncaptured),0)::bigint AS suspected_uncaptured,
       COALESCE(sum(f.exam_records-f.suspected_uncaptured),0)::bigint AS what_if_exams,
       count(*) FILTER (WHERE f.suspected_uncaptured>0)::bigint AS candidate_groups,
       COALESCE(sum(f.exam_records) FILTER (WHERE NOT f.matching_keys_complete),0)::bigint AS unmatchable_exams,
       COALESCE(sum(f.exam_records) FILTER (WHERE f.exam_records>1 AND f.captured_exams=0),0)::bigint AS repeated_without_capture
FROM mart.investigation_groups f LEFT JOIN dw.dim_modality m USING (modality_id)
WHERE {where};
