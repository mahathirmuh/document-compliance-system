import type {
  SectionAliasListParams,
  SectionAliasProfileListParams,
  SectionDefinitionListParams,
} from '../types/sectionDefinition';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) =>
  ['section-definitions', scope[0], scope[1]] as const;

export const sectionDefinitionKeys = {
  all: root,
  profiles: (scope: DocumentSessionScope) => [...root(scope), 'profiles'] as const,
  profileList: (scope: DocumentSessionScope, params: SectionAliasProfileListParams) =>
    [...root(scope), 'profiles', params] as const,
  definitions: (scope: DocumentSessionScope) =>
    [...root(scope), 'definitions'] as const,
  definitionList: (scope: DocumentSessionScope, params: SectionDefinitionListParams) =>
    [...root(scope), 'definitions', params] as const,
  aliases: (scope: DocumentSessionScope) => [...root(scope), 'aliases'] as const,
  aliasList: (scope: DocumentSessionScope, params: SectionAliasListParams) =>
    [...root(scope), 'aliases', params] as const,
} as const;
