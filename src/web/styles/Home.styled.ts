import styled from 'styled-components';

export const MobileHeroBanner = styled.div`
  height: 200px;
  background: url(/images/folded-clothes-on-white-chair-wide.jpg) no-repeat top center;
  background-size: cover;
`;

export const DesktopHeroBanner = styled.div`
  background: url(/images/folded-clothes-on-white-chair.jpg) no-repeat center;
  background-size: cover;
  width: 33.33%;
`;

export const Container = styled.div`
  width: 100%;
  padding-right: 15px;
  padding-left: 15px;
  margin-right: auto;
  margin-left: auto;
`;

export const Row = styled.div`
  display: flex;
  flex-wrap: wrap;
  margin-right: -15px;
  margin-left: -15px;
`;

export const Content = styled.div`
  width: 66.66%;
  box-sizing: border-box;
`;

export const HotProducts = styled.div`
  padding: 32px 10% 70px;
`;

export const Home = styled.div`
  @media (min-width: 992px) {
    ${Container} {
      height: calc(100vh - 91px);
    }

    ${DesktopHeroBanner} {
      height: calc(100vh - 91px);
    }

    ${Content} {
      height: calc(100vh - 91px);
      overflow-y: scroll;
    }

    ${MobileHeroBanner} {
      display: none;
    }
  }

  @media (max-width: 992px) {
    ${DesktopHeroBanner} {
      display: none;
    }

    ${Content} {
      width: 100%;
    }
  }
`;
