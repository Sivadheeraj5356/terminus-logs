use crate::types::account::Role;

#[derive(Clone, Copy, PartialEq)]
pub enum Permission {
    ValidatorRegister,
    ValidatorView,
    ValidatorManage,
    ValidatorSlash,
    BlockCreate,
    BlockView,
    BlockEndorse,
    ReferendumCreate,
    ReferendumView,
    ReferendumManage,
    BallotGrantManage,
    GovVoteCast,
    GovVoteBroad,
    RelayerView,
    RelayerManage,
    MonitoringView,
    AuditView,
    AccountAdmin,
}

pub fn permits(role: Role, permission: Permission) -> bool {
    match role {
        Role::Participant => matches!(
            permission,
            Permission::ValidatorRegister
                | Permission::ValidatorView
                | Permission::ValidatorManage
                | Permission::BlockCreate
                | Permission::BlockView
                | Permission::BlockEndorse
                | Permission::ReferendumCreate
                | Permission::ReferendumView
                | Permission::BallotGrantManage
                | Permission::GovVoteCast
        ),
        Role::Operator => matches!(
            permission,
            Permission::ValidatorRegister
                | Permission::ValidatorView
                | Permission::ValidatorManage
                | Permission::ValidatorSlash
                | Permission::BlockCreate
                | Permission::BlockView
                | Permission::BlockEndorse
                | Permission::ReferendumCreate
                | Permission::ReferendumView
                | Permission::ReferendumManage
                | Permission::BallotGrantManage
                | Permission::GovVoteCast
                | Permission::GovVoteBroad
                | Permission::RelayerView
                | Permission::RelayerManage
                | Permission::MonitoringView
                | Permission::AuditView
        ),
        Role::Admin => true,
    }
}
