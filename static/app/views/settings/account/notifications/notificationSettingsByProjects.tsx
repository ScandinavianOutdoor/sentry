import React from 'react';
import styled from '@emotion/styled';

import AsyncComponent from 'app/components/asyncComponent';
import Pagination from 'app/components/pagination';
import {t} from 'app/locale';
import space from 'app/styles/space';
import {Project} from 'app/types';
import AsyncView from 'app/views/asyncView';
import {
  MIN_PROJECTS_FOR_PAGINATION,
  MIN_PROJECTS_FOR_SEARCH,
  NotificationSettingsByProviderObject,
  NotificationSettingsObject,
} from 'app/views/settings/account/notifications/constants';
import {
  getParentData,
  getParentField,
  groupByOrganization,
} from 'app/views/settings/account/notifications/utils';
import EmptyMessage from 'app/views/settings/components/emptyMessage';
import Form from 'app/views/settings/components/forms/form';
import JsonForm from 'app/views/settings/components/forms/jsonForm';

type Props = {
  notificationType: string;
  notificationSettings: NotificationSettingsObject;
  onChange: (
    changedData: NotificationSettingsByProviderObject,
    parentId: string
  ) => NotificationSettingsObject;
} & AsyncComponent['props'];

type State = {
  projects: Project[];
} & AsyncComponent['state'];

class NotificationSettingsByProjects extends AsyncComponent<Props, State> {
  getDefaultState(): State {
    return {
      ...super.getDefaultState(),
      projects: [],
    };
  }

  getEndpoints(): ReturnType<AsyncComponent['getEndpoints']> {
    return [['projects', '/projects/']];
  }

  getProjectCount = (): number => {
    /** Check the notification settings for how many projects there are. */
    const {notificationType, notificationSettings} = this.props;

    return Object.values(notificationSettings[notificationType]?.project || {}).length;
  };

  getGroupedProjects = (): {[key: string]: Project[]} => {
    /**
     * The UI expects projects to be grouped by organization but can also use
     * this function to make a single group with all organizations.
     */
    const {projects: stateProjects} = this.state;

    return Object.fromEntries(
      Object.values(
        groupByOrganization(stateProjects)
      ).map(({organization, projects}) => [`${organization.name} Projects`, projects])
    );
  };

  renderBody() {
    const {notificationType, notificationSettings, onChange} = this.props;
    const {projects, projectsPageLinks} = this.state;

    const canSearch = this.getProjectCount() >= MIN_PROJECTS_FOR_SEARCH;
    const shouldPaginate = projects.length >= MIN_PROJECTS_FOR_PAGINATION;

    type RenderSearch = React.ComponentProps<
      typeof AsyncView.prototype.renderSearchInput
    >['children'];

    // eslint-disable-next-line react/prop-types
    const renderSearch: RenderSearch = ({defaultSearchBar}) => (
      <SearchWrapper>{defaultSearchBar}</SearchWrapper>
    );

    return (
      <React.Fragment>
        {canSearch &&
          this.renderSearchInput({
            stateKey: 'projects',
            url: '/projects/',
            placeholder: t('Search Projects'),
            children: renderSearch,
          })}
        <Form
          saveOnBlur
          apiMethod="PUT"
          apiEndpoint="/users/me/notification-settings/"
          initialData={getParentData(notificationType, notificationSettings, projects)}
        >
          {projects.length === 0 ? (
            <EmptyMessage>{t('No projects found')}</EmptyMessage>
          ) : (
            Object.entries(this.getGroupedProjects()).map(([groupTitle, parents]) => (
              <JsonForm
                key={groupTitle}
                title={groupTitle}
                fields={parents.map(parent =>
                  getParentField(notificationType, notificationSettings, parent, onChange)
                )}
              />
            ))
          )}
        </Form>
        {canSearch && shouldPaginate && (
          <Pagination pageLinks={projectsPageLinks} {...this.props} />
        )}
      </React.Fragment>
    );
  }
}

const SearchWrapper = styled('div')`
  display: flex;
  * {
    width: 100%;
  }
  grid-template-columns: 1fr max-content;
  grid-gap: ${space(1.5)};
  margin-top: ${space(4)};
  margin-bottom: ${space(1)};
  position: relative;
`;

export default NotificationSettingsByProjects;
