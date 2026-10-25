import { Composition } from 'remotion';
import { DemoVideo } from './DemoVideo';

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={1800}
        fps={30}
        width={1280}
        height={800}
      />
    </>
  );
};
