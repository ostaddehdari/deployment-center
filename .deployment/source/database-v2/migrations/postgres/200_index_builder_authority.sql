\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path TO zoha,public;

-- Preserve both the published version and any independent draft edits.
DO $$
DECLARE f record; oldv record; new_id uuid; next_version integer; new_active integer; new_draft integer;
BEGIN
 FOR f IN SELECT * FROM index_forms WHERE active AND NOT deleted LOOP
  SELECT COALESCE(max(version),0)+1 INTO next_version FROM index_form_versions WHERE index_form_id=f.id;
  new_active:=0;new_draft:=NULL;
  FOR oldv IN SELECT v.*,chosen.kind FROM index_form_versions v CROSS JOIN LATERAL (VALUES('active',f.active_version),('draft',f.draft_version)) chosen(kind,version) WHERE v.index_form_id=f.id AND v.version=chosen.version AND v.active AND NOT v.deleted ORDER BY chosen.kind LOOP
   INSERT INTO index_form_versions(index_form_id,version,schema_snapshot,validation_rules,immutable,published_at,created_by,updated_by,active,deleted)
   VALUES(f.id,next_version,COALESCE(oldv.schema_snapshot,'{}')||'{"source":"index-builder","hierarchyDepth":3}'::jsonb,oldv.validation_rules,oldv.kind='active',CASE WHEN oldv.kind='active' THEN now() ELSE NULL END,oldv.created_by,oldv.updated_by,true,false) RETURNING id INTO new_id;
   INSERT INTO index_form_fields(version_id,field_key,label,help_text,placeholder,input_kind,value_kind,required,search_enabled,index_enabled,display_order,width,config,validation,created_by,updated_by,active,deleted)
   SELECT new_id,ff.field_key,ff.label,ff.help_text,ff.placeholder,ff.input_kind,ff.value_kind,ff.required,ff.search_enabled,ff.index_enabled,ff.display_order,ff.width,
    ff.config||jsonb_build_object('authority','index-builder','hierarchy',jsonb_build_object('parentKey',COALESCE(ff.config->'hierarchy'->>'parentKey',parent.field_key))),ff.validation,ff.created_by,ff.updated_by,true,false
   FROM index_form_fields ff
   LEFT JOIN index_form_fields parent ON parent.version_id=ff.version_id AND parent.active AND NOT parent.deleted
    AND parent.config->'runtime'->>'taxonomyCode'=CASE WHEN ff.config->'runtime'->>'taxonomyCode' IN ('IDX-002','IDX-003') THEN 'IDX-001' ELSE ff.config->'runtime'->>'parentTaxonomyCode' END
   WHERE ff.version_id=oldv.id AND ff.active AND NOT ff.deleted;
   INSERT INTO index_form_options(field_id,value_key,label,sort_order,is_active,created_by,updated_by,active,deleted)
   SELECT nf.id,o.value_key,o.label,o.sort_order,o.is_active,o.created_by,o.updated_by,true,false FROM index_form_fields ofld JOIN index_form_options o ON o.field_id=ofld.id AND o.active AND NOT o.deleted JOIN index_form_fields nf ON nf.version_id=new_id AND nf.field_key=ofld.field_key WHERE ofld.version_id=oldv.id;
   INSERT INTO index_form_rules(version_id,rule_key,rule_kind,condition,action,sort_order,created_by,updated_by,active,deleted)
   SELECT new_id,rule_key,rule_kind,condition,action,sort_order,created_by,updated_by,true,false FROM index_form_rules WHERE version_id=oldv.id AND active AND NOT deleted;
   IF oldv.kind='active' THEN new_active:=next_version; END IF;
   IF oldv.kind='draft' THEN new_draft:=next_version; END IF;
   next_version:=next_version+1;
  END LOOP;
  IF new_draft IS NOT NULL THEN UPDATE index_forms SET active_version=new_active,draft_version=new_draft,settings=COALESCE(settings,'{}')||'{"authority":"index-builder"}'::jsonb WHERE id=f.id; END IF;
 END LOOP;
END $$;

CREATE OR REPLACE VIEW index_builder_published_fields AS
SELECT ct.code AS content_type,f.id AS form_id,f.active_version,ff.id AS field_id,ff.field_key,ff.label,ff.input_kind,ff.value_kind,ff.required,ff.search_enabled,ff.index_enabled,ff.display_order,ff.width,ff.help_text,ff.placeholder,ff.config,ff.validation,
 ff.config->'runtime'->>'taxonomyCode' AS taxonomy_code,
 parent.field_key AS parent_key,parent.config->'runtime'->>'taxonomyCode' AS parent_taxonomy_code
FROM content_types ct
JOIN content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
JOIN index_forms f ON f.id=m.index_form_id AND f.active AND NOT f.deleted AND f.is_active
JOIN index_form_versions v ON v.index_form_id=f.id AND v.version=f.active_version AND v.active AND NOT v.deleted
JOIN index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
LEFT JOIN index_form_fields parent ON parent.version_id=v.id AND parent.field_key=ff.config->'hierarchy'->>'parentKey' AND parent.active AND NOT parent.deleted
WHERE ct.active AND NOT ct.deleted;

-- Compatibility consumers receive a projection of the builder's published definition.
-- These tables are storage/projections; they no longer define forms or relationships.
CREATE OR REPLACE FUNCTION sync_index_builder_projection(wanted_form uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO zoha.index_runtime_taxonomies(code,title,field_type,is_multi,allows_personal,metadata,is_active)
 SELECT DISTINCT ON(taxonomy_code) taxonomy_code,label,
  CASE WHEN input_kind IN ('searchable_select','select','multiselect','radio','checkbox','tags') THEN 'taxonomy' WHEN input_kind='textarea' THEN 'textarea' ELSE 'text' END,
  input_kind IN ('multiselect','checkbox','tags'),COALESCE((config->'runtime'->>'allowsPersonal')::boolean,false),
  jsonb_build_object('authority','index-builder','parentTaxonomyCode',parent_taxonomy_code),true
 FROM zoha.index_builder_published_fields WHERE form_id=wanted_form AND COALESCE(taxonomy_code,'')<>'' ORDER BY taxonomy_code,content_type
 ON CONFLICT(code) DO UPDATE SET title=EXCLUDED.title,field_type=EXCLUDED.field_type,is_multi=EXCLUDED.is_multi,allows_personal=EXCLUDED.allows_personal,metadata=zoha.index_runtime_taxonomies.metadata||EXCLUDED.metadata,is_active=true,updated_at=now();
 DELETE FROM zoha.index_runtime_post_type_fields p USING zoha.content_type_index_forms m,zoha.content_types ct WHERE m.index_form_id=wanted_form AND m.is_primary AND m.active AND NOT m.deleted AND ct.id=m.content_type_id AND p.post_type_code=ct.code;
 INSERT INTO zoha.index_runtime_post_type_fields(post_type_code,taxonomy_code,sort_order,is_required,settings)
 SELECT content_type,taxonomy_code,display_order,required,config||jsonb_build_object('label',label,'helpText',help_text,'placeholder',placeholder,'width',width,'parentKey',parent_key,'parentTaxonomyCode',parent_taxonomy_code,'authority','index-builder')
 FROM zoha.index_builder_published_fields WHERE form_id=wanted_form AND COALESCE(taxonomy_code,'')<>'';
END $$;
SELECT sync_index_builder_projection(id) FROM index_forms WHERE active AND NOT deleted AND active_version>0;

-- Preserve existing vocabulary IDs and attach unambiguous historical parents.
UPDATE index_runtime_terms child SET parent_id=parent.id FROM index_runtime_taxonomies definition,index_runtime_terms parent
WHERE child.taxonomy_code=definition.code AND child.parent_id IS NULL AND child.parent_hint IS NOT NULL
 AND parent.taxonomy_code=definition.metadata->>'parentTaxonomyCode' AND parent.normalized_title=child.parent_hint AND parent.is_active
 AND (SELECT count(*) FROM index_runtime_terms candidate WHERE candidate.taxonomy_code=parent.taxonomy_code AND candidate.normalized_title=parent.normalized_title AND candidate.is_active)=1;

ALTER TABLE index_runtime_terms DROP CONSTRAINT IF EXISTS index_runtime_terms_taxonomy_code_normalized_title_parent_h_key;
CREATE UNIQUE INDEX index_builder_term_parent_unique ON index_runtime_terms(taxonomy_code,normalized_title,parent_id,parent_hint);

INSERT INTO schema_migrations(version,checksum) VALUES('200_index_builder_authority','index-builder-authority-v060') ON CONFLICT(version) DO NOTHING;
COMMIT;
